import os
import re
import secrets
from typing import Any
import time
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

import html as html_lib
from xml.sax.saxutils import escape as xml_escape

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

try:
    from .env_loader import env_bool, env_int, load_env_file
    from .store import (
        BlogStore,
        PostVersionConflict,
        UPLOADS_DIR,
        estimate_read_time,
        is_allowed_public_upload_path,
        render_markdown,
    )
except ImportError:
    from env_loader import env_bool, env_int, load_env_file
    from store import (
        BlogStore,
        PostVersionConflict,
        UPLOADS_DIR,
        estimate_read_time,
        is_allowed_public_upload_path,
        render_markdown,
    )


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT_DIR / "frontend" / "dist"
load_env_file(ROOT_DIR / ".env")


def normalize_admin_prefix(raw_value: str | None) -> str:
    value = (raw_value or "/admin").strip() or "/admin"
    if not value.startswith("/"):
        value = f"/{value}"
    value = value.rstrip("/")
    return value or "/admin"


def is_safe_admin_next(target: str | None, admin_prefix: str) -> bool:
    if not target:
        return False
    parsed = urlsplit(target)
    return (
        not parsed.scheme
        and not parsed.netloc
        and parsed.path.startswith(f"{admin_prefix}/")
    )


def summarize_post(post):
    """Public list payload used by the current Vue frontend."""
    return {
        "slug": post["slug"],
        "title": post["title"],
        "excerpt": post["excerpt"],
        "published_at": post["published_at"],
        "read_time": post["read_time"],
        "category": post["category"],
        "tags": post["tags"],
        "cover_image": post.get("cover_image") or "",
        "click_count": int(post.get("click_count") or 0),
    }


def summarize_related_post(post):
    return {
        "slug": post["slug"],
        "title": post["title"],
        "excerpt": post["excerpt"],
        "category": post["category"],
    }


def summarize_adjacent_post(post):
    return {
        "slug": post["slug"],
        "title": post["title"],
    }


def build_post_detail_payload(post, *, related_posts, previous_post, next_post):
    return {
        "slug": post["slug"],
        "title": post["title"],
        "excerpt": post["excerpt"],
        "published_at": post["published_at"],
        "read_time": post["read_time"],
        "category": post["category"],
        "tags": post["tags"],
        "hero_quote": post["hero_quote"],
        "cover_image": post.get("cover_image") or "",
        "html_content": post.get("html_content") or "",
        "sections": post.get("sections") or [],
        "related_posts": related_posts,
        "previous_post": previous_post,
        "next_post": next_post,
    }


def build_profile_form(profile):
    social_links = {item.get("label"): item for item in profile.get("social_links", [])}
    github = social_links.get("GitHub 仓库", {})
    return {
        **profile,
        "github_label": github.get("value", ""),
        "github_url": github.get("url", ""),
        "about_intro_text": "\n".join(profile.get("about_intro", [])),
        "update_calendar_text": "\n".join(
            f"{item.get('date', '')} | {item.get('title', '')}"
            for item in profile.get("update_calendar", [])
        ),
    }


def form_value(source, key: str, default: str = "") -> str:
    """Read a form/json field as a stripped string without raising on bad types."""
    if source is None:
        return default
    try:
        value = source.get(key, default)
    except Exception:
        return default
    if value is None:
        return default
    return str(value).strip()


def build_edit_post(post):
    if not post:
        return {
            "id": "",
            "title": "",
            "slug": "",
            "excerpt": "",
            "published_at": "",
            "read_time": "",
            "category": "",
            "tags_text": "",
            "hero_quote": "",
            "cover_image": "",
            "markdown_content": "",
            "html_content": "",
            "status": "draft",
        }

    return {
        **post,
        "tags_text": ", ".join(post.get("tags", [])),
    }


DEFAULT_SECRET_KEY = "dev-secret-key-change-me"
DEFAULT_ADMIN_PASSWORD = "admin123456"
LOGIN_FAILURE_MAX_KEYS = 2048


def validate_launch_config(
    *,
    debug_mode: bool,
    secret_key: str,
    admin_password: str,
    admin_prefix: str,
    public_base_url: str,
    cookie_secure: bool,
    require_public_base_url: bool = False,
) -> None:
    if debug_mode:
        return

    if not secret_key or secret_key == DEFAULT_SECRET_KEY:
        raise RuntimeError(
            "BLOG_SECRET_KEY 仍是默认值或过短，请在 .env 中改为随机的长密钥。"
        )
    if (
        not admin_password
        or len(admin_password) < 12
        or admin_password in {DEFAULT_ADMIN_PASSWORD, "123", "123456", "admin", "password", "change-me-before-deploy"}
    ):
        raise RuntimeError(
            "BLOG_ADMIN_PASSWORD 太弱或仍是默认值，请在 .env 中改为至少 12 位的强密码。"
        )
    if admin_prefix == "/admin" or not admin_prefix.startswith("/"):
        raise RuntimeError(
            "BLOG_ADMIN_PREFIX 不能使用默认的 /admin，请改成不易猜到且以 / 开头的路径。"
        )
    if require_public_base_url and not public_base_url:
        raise RuntimeError(
            "上线模式要求配置 BLOG_PUBLIC_BASE_URL 为真实的 HTTPS 公开域名。"
        )
    if public_base_url:
        if not public_base_url.startswith("https://"):
            raise RuntimeError(
                "BLOG_PUBLIC_BASE_URL 必须以 https:// 开头。"
            )
        if not cookie_secure:
            raise RuntimeError(
                "站点已使用 HTTPS，必须同时设置 BLOG_COOKIE_SECURE=true。"
            )


def create_app():
    app = Flask(__name__)
    debug_mode = env_bool("BLOG_DEBUG", False)
    secret_key = os.getenv("BLOG_SECRET_KEY", DEFAULT_SECRET_KEY)
    admin_password = os.getenv("BLOG_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    admin_prefix = normalize_admin_prefix(os.getenv("BLOG_ADMIN_PREFIX", "/admin"))
    public_base_url = (os.getenv("BLOG_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    require_public_base_url = env_bool("BLOG_REQUIRE_PUBLIC_BASE_URL", False)
    cookie_secure = env_bool("BLOG_COOKIE_SECURE", False)
    validate_launch_config(
        debug_mode=debug_mode,
        secret_key=secret_key,
        admin_password=admin_password,
        admin_prefix=admin_prefix,
        public_base_url=public_base_url,
        cookie_secure=cookie_secure,
        require_public_base_url=require_public_base_url,
    )

    app.secret_key = secret_key
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=cookie_secure,
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(
            seconds=env_int("BLOG_SESSION_LIFETIME_SECONDS", 8 * 60 * 60, minimum=300)
        ),
        SESSION_REFRESH_EACH_REQUEST=True,
        MAX_CONTENT_LENGTH=env_int("BLOG_MAX_UPLOAD_BYTES", 10 * 1024 * 1024, minimum=1),
        BLOG_DEBUG=debug_mode,
        BLOG_ADMIN_PASSWORD=admin_password,
        BLOG_REQUIRE_PUBLIC_BASE_URL=require_public_base_url,
    )
    admin_path = admin_prefix.lstrip("/")
    app.config["ADMIN_PREFIX"] = admin_prefix

    store = BlogStore()
    store.init()
    store.purge_expired_trash(retention_days=30)
    login_failures: dict[str, list[float]] = {}
    csrf_session_key = "_admin_csrf_token"
    login_window_seconds = env_int("BLOG_LOGIN_RATE_WINDOW_SECONDS", 300, minimum=60)
    login_max_attempts = env_int("BLOG_LOGIN_MAX_ATTEMPTS", 5, minimum=1)
    trusted_proxy_count = env_int("BLOG_TRUSTED_PROXY_COUNT", 0, minimum=0)

    def is_authenticated():
        return session.get("admin_authenticated") is True

    def is_admin_api_request() -> bool:
        return request.path.startswith(f"{admin_prefix}/api/")

    def api_error(code: str, error: str, status: int):
        return jsonify({"ok": False, "code": code, "error": error}), status

    def csrf_token() -> str:
        token = session.get(csrf_session_key)
        if not token:
            token = secrets.token_urlsafe(32)
            session[csrf_session_key] = token
        return token

    def valid_csrf_token(candidate: str | None) -> bool:
        expected = session.get(csrf_session_key)
        return bool(expected and candidate and secrets.compare_digest(str(candidate), str(expected)))

    def client_key() -> str:
        remote = (request.remote_addr or "").strip() or "unknown"
        if trusted_proxy_count <= 0:
            return remote
        chain = [item.strip() for item in (request.headers.get("X-Forwarded-For") or "").split(",") if item.strip()]
        if not chain:
            return remote
        index = max(0, len(chain) - trusted_proxy_count)
        return chain[index] or remote

    def prune_login_failures(now: float) -> None:
        for key in [k for k, stamps in login_failures.items()
                    if not stamps or now - stamps[-1] >= login_window_seconds]:
            login_failures.pop(key, None)
        overflow = len(login_failures) - LOGIN_FAILURE_MAX_KEYS
        if overflow > 0:
            for key, _ in sorted(login_failures.items(), key=lambda item: item[1][-1])[:overflow]:
                login_failures.pop(key, None)

    def login_rate_limited() -> tuple[bool, int]:
        now = time.monotonic()
        key = client_key()
        prune_login_failures(now)
        attempts = [stamp for stamp in login_failures.get(key, []) if now - stamp < login_window_seconds]
        if not attempts:
            login_failures.pop(key, None)
            return False, 0
        login_failures[key] = attempts
        if len(attempts) < login_max_attempts:
            return False, 0
        retry_after = max(1, int(login_window_seconds - (now - attempts[0])))
        return True, retry_after

    def register_login_failure() -> None:
        now = time.monotonic()
        key = client_key()
        attempts = [stamp for stamp in login_failures.get(key, []) if now - stamp < login_window_seconds]
        attempts.append(now)
        login_failures[key] = attempts[-login_max_attempts:]
        prune_login_failures(now)

    @app.context_processor
    def inject_admin_security_context():
        return {"csrf_token": csrf_token}

    @app.before_request
    def protect_admin_mutations():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if not (request.path == admin_prefix or request.path.startswith(f"{admin_prefix}/")):
            return None
        if is_admin_api_request() and not is_authenticated():
            return api_error("auth_required", "登录状态已失效，请重新登录。", 401)
        candidate = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if valid_csrf_token(candidate):
            return None
        if is_admin_api_request() or request.is_json:
            return api_error("csrf_failed", "请求校验已失效，请刷新页面后重试。", 400)
        flash("请求校验已失效，请刷新页面后重试。", "error")
        return redirect(request.referrer or url_for("admin_login"))

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" in content_type:
            # Admin templates still rely on small inline scripts/styles.
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "img-src 'self' data: blob: https:; "
                "style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'",
            )
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(error):
        if is_admin_api_request() or request.is_json:
            return api_error("payload_too_large", "上传内容过大，请压缩文件后重试。", 413)
        flash("上传内容过大，请压缩文件后重试。", "error")
        return redirect(request.referrer or url_for("admin_login"))

    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith("/api/") or is_admin_api_request():
            return api_error("not_found", "请求的内容不存在。", 404)
        return error

    @app.errorhandler(500)
    def handle_server_error(error):
        if request.path.startswith("/api/") or is_admin_api_request():
            return api_error("server_error", "服务暂时不可用，请稍后重试。", 500)
        return error

    def admin_required(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not is_authenticated():
                if is_admin_api_request() or request.is_json:
                    return api_error("auth_required", "登录状态已失效，请重新登录。", 401)
                return redirect(url_for("admin_login", next=request.path))
            session.permanent = True
            return view_func(*args, **kwargs)

        return wrapped

    @app.get("/api/health")
    def healthcheck():
        return jsonify({"status": "ok"})

    @app.get("/api/site")
    def site():
        return jsonify(store.get_site_payload())

    @app.get("/api/posts")
    def posts():
        tag = request.args.get("tag")
        limit = request.args.get("limit", type=int)
        sort = request.args.get("sort", "latest")
        q = (request.args.get("q") or "").strip()
        page = request.args.get("page", type=int)

        list_kwargs = {
            "tag": tag,
            "published_only": True,
            "sort": sort,
            "search": q or None,
        }

        if page is None:
            if limit is not None:
                list_kwargs["limit"] = max(1, min(limit, 50))
            data = store.list_posts(**list_kwargs)
            return jsonify([summarize_post(post) for post in data])

        page = max(1, page)
        per_page = max(1, min(limit or 10, 50))
        start = (page - 1) * per_page
        total = store.count_posts(
            tag=tag,
            published_only=True,
            search=q or None,
        )
        items = store.list_posts(**list_kwargs, limit=per_page, offset=start)
        return jsonify(
            {
                "items": [summarize_post(post) for post in items],
                "total": total,
                "page": page,
                "per_page": per_page,
                "has_more": start + per_page < total,
            }
        )

    @app.get("/api/posts/<slug>")
    def post_detail(slug):
        match = store.get_post_by_slug(slug)
        if match is None:
            abort(404)

        # Count a view once per browser session per slug to avoid double counting
        # when the SPA mounts/remounts the same article during a single session.
        viewed = session.get("viewed_posts") or []
        if not isinstance(viewed, list):
            viewed = []
        if slug not in viewed:
            match["click_count"] = store.increment_post_click(slug)
            viewed = (viewed + [slug])[-80:]
            session["viewed_posts"] = viewed
            session.modified = True

        previous_match, next_match = store.get_adjacent_posts(match)
        previous_post = summarize_adjacent_post(previous_match) if previous_match else None
        next_post = summarize_adjacent_post(next_match) if next_match else None
        related_posts = [
            summarize_related_post(post)
            for post in store.get_related_posts(match, limit=2)
        ]

        return jsonify(
            build_post_detail_payload(
                match,
                related_posts=related_posts,
                previous_post=previous_post,
                next_post=next_post,
            )
        )

    @app.get("/uploads/<path:path>")
    def uploads(path):
        if not is_allowed_public_upload_path(path):
            abort(404)

        response = send_from_directory(UPLOADS_DIR, path)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    @app.route(f"{admin_prefix}/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            limited, retry_after = login_rate_limited()
            if limited:
                if request.is_json:
                    return api_error("login_rate_limited", "登录尝试过多，请稍后再试。", 429)
                flash("登录尝试过多，请稍后再试。", "error")
                return render_template("admin_login.html"), 429, {"Retry-After": str(retry_after)}

            password = form_value(request.form, "password")
            expected = app.config.get("BLOG_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
            if secrets.compare_digest(password, expected):
                login_failures.pop(client_key(), None)
                session.clear()
                session.permanent = True
                session["admin_authenticated"] = True
                csrf_token()
                flash("已进入管理后台。", "success")
                next_target = request.args.get("next")
                if not is_safe_admin_next(next_target, admin_prefix):
                    next_target = url_for("admin_dashboard")
                return redirect(next_target)

            register_login_failure()
            flash("密码错误，请重试。", "error")

        return render_template("admin_login.html")

    @app.post(f"{admin_prefix}/logout")
    @admin_required
    def admin_logout():
        session.clear()
        flash("你已退出后台。", "success")
        return redirect(url_for("admin_login"))

    def build_admin_context(**extra):
        stats = store.stats()
        stats["admin_prefix"] = admin_prefix
        return {"stats": stats, **extra}

    @app.get(admin_prefix)
    @admin_required
    def admin_dashboard():
        store.purge_expired_trash(retention_days=30)
        return render_template(
            "admin_dashboard.html",
            **build_admin_context(admin_posts=store.list_admin_posts()),
        )

    @app.get(f"{admin_prefix}/write", defaults={"post_id": None})
    @app.get(f"{admin_prefix}/write/<int:post_id>")
    @admin_required
    def admin_write(post_id):
        post = store.get_post_by_id(post_id) if post_id else None
        if post_id and post is None:
            abort(404)
        if post and post.get("status") == "trashed":
            flash("请先从稿件总览恢复文章，再继续编辑。", "error")
            return redirect(url_for("admin_dashboard"))
        return render_template(
            "admin_write.html",
            **build_admin_context(edit_post=build_edit_post(post)),
        )

    @app.get(f"{admin_prefix}/media")
    @admin_required
    def admin_media():
        return render_template(
            "admin_media.html",
            **build_admin_context(media_assets=store.list_media_assets()),
        )

    @app.get(f"{admin_prefix}/profile")
    @admin_required
    def admin_profile_page():
        profile = store.get_site_profile()
        return render_template(
            "admin_profile.html",
            **build_admin_context(
                profile_form=build_profile_form(profile),
                profile=profile,
            ),
        )

    @app.post(f"{admin_prefix}/profile")
    @admin_required
    def admin_profile():
        try:
            store.update_site_profile(request.form, request.files.get("avatar"))
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("个人资料已更新。", "success")
        return redirect(url_for("admin_profile_page"))

    @app.post(f"{admin_prefix}/posts/save")
    @admin_required
    def admin_save_post():
        post_id = request.form.get("post_id", type=int)
        action = form_value(request.form, "action", "draft") or "draft"
        existing = store.get_post_by_id(post_id) if post_id else None
        if existing and existing.get("status") == "trashed":
            flash("回收站文章不能直接保存，请先恢复为草稿。", "error")
            return redirect(url_for("admin_dashboard"))
        try:
            saved_id = store.save_post(request.form, post_id=post_id, action=action)
        except ValueError as exc:
            flash(str(exc), "error")
            submitted = build_edit_post(existing)
            submitted.update({
                "id": post_id or "",
                "title": form_value(request.form, "title"),
                "slug": form_value(request.form, "slug"),
                "excerpt": form_value(request.form, "excerpt"),
                "published_at": form_value(request.form, "published_at"),
                "read_time": form_value(request.form, "read_time"),
                "category": form_value(request.form, "category"),
                "tags_text": form_value(request.form, "tags"),
                "hero_quote": form_value(request.form, "hero_quote"),
                "cover_image": form_value(request.form, "cover_image"),
                "markdown_content": str(request.form.get("markdown_content") or ""),
                "html_content": render_markdown(str(request.form.get("markdown_content") or "")),
                "status": (existing or {}).get("status", "draft"),
            })
            return render_template(
                "admin_write.html",
                **build_admin_context(edit_post=submitted),
            ), 400

        message = ('已保存为草稿（前台不可见）。若要上线，请点击「发布文章」。' if action == "draft" else '文章已发布，前台现在可以看到。')
        flash(message, "success")
        return redirect(url_for("admin_write", post_id=saved_id, saved=1))

    @app.post(f"{admin_prefix}/posts/<int:post_id>/delete")
    @admin_required
    def admin_delete_post(post_id):
        try:
            store.trash_post(post_id)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("文章已移入回收站，30 天内可以恢复。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.post(f"{admin_prefix}/posts/<int:post_id>/restore")
    @admin_required
    def admin_restore_post(post_id):
        try:
            store.restore_post(post_id)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("文章已恢复为草稿。", "success")
        return redirect(url_for("admin_dashboard"))

    @app.post(f"{admin_prefix}/api/autosave")
    @admin_required
    def admin_autosave():
        payload = request.get_json(silent=True) or {}
        raw_post_id = payload.get("post_id")
        try:
            post_id = int(raw_post_id) if raw_post_id else None
        except (TypeError, ValueError):
            return api_error("invalid_post_id", "\u7a3f\u4ef6 ID \u65e0\u6548\u3002", 400)

        if post_id:
            existing = store.get_post_by_id(post_id)
            if existing is None:
                return api_error("post_not_found", "\u7a3f\u4ef6\u4e0d\u5b58\u5728\u3002", 404)
            if existing.get("status") != "draft":
                return api_error("published_autosave_blocked", "\u5df2\u53d1\u5e03\u6587\u7ae0\u4ec5\u4fdd\u5b58\u5728\u672c\u5730\uff0c\u4e0d\u4f1a\u81ea\u52a8\u8986\u76d6\u7ebf\u4e0a\u5185\u5bb9\u3002", 409)

        form_data = payload.get("fields") or {}
        if not isinstance(form_data, dict):
            return api_error("invalid_payload", "\u81ea\u52a8\u4fdd\u5b58\u6570\u636e\u683c\u5f0f\u65e0\u6548\u3002", 400)
        if not str(form_data.get("title") or "").strip():
            return api_error("title_required", "\u586b\u5199\u6807\u9898\u540e\u624d\u4f1a\u81ea\u52a8\u4fdd\u5b58\u5230\u670d\u52a1\u5668\u3002", 400)

        expected_updated_at = payload.get("updated_at")
        try:
            saved_id = store.save_post(
                form_data,
                post_id=post_id,
                action="draft",
                expected_updated_at=expected_updated_at,
                create_revision=False,
            )
        except PostVersionConflict as exc:
            return api_error("version_conflict", str(exc), 409)
        except ValueError as exc:
            return api_error("validation_error", str(exc), 400)

        saved_post = store.get_post_by_id(saved_id)
        return jsonify(
            {
                "id": saved_id,
                "slug": saved_post.get("slug", ""),
                "status": saved_post.get("status", "draft"),
                "updated_at": saved_post.get("updated_at", ""),
                "read_time": saved_post.get("read_time", ""),
                "excerpt": saved_post.get("excerpt", ""),
            }
        )

    @app.post(f"{admin_prefix}/api/preview-markdown")
    @admin_required
    def admin_preview_markdown():
        payload = request.get_json(silent=True) or {}
        markdown_content = payload.get("markdown_content", "")
        if not isinstance(markdown_content, str):
            return api_error("invalid_payload", "Markdown 内容格式无效。", 400)
        if len(markdown_content) > 500_000:
            return api_error("content_too_large", "Markdown 内容过长。", 400)
        return jsonify(
            {
                "html": render_markdown(markdown_content),
                "read_time": estimate_read_time(markdown_content),
                "excerpt": store.build_excerpt(markdown_content),
            }
        )

    @app.post(f"{admin_prefix}/api/import-markdown")
    @admin_required
    def admin_import_markdown():
        markdown_file = request.files.get("markdown_file")
        if markdown_file is None or not markdown_file.filename:
            return api_error("validation_error", "请选择一个 Markdown 文件。", 400)
        try:
            payload = store.import_markdown(markdown_file)
        except ValueError as exc:
            return api_error("validation_error", str(exc), 400)
        return jsonify(payload)

    @app.post(f"{admin_prefix}/api/upload-image")
    @admin_required
    def admin_upload_image():
        image_file = request.files.get("image")
        if image_file is None or not image_file.filename:
            return api_error("validation_error", "请选择一张图片。", 400)
        try:
            payload = store.upload_media(image_file)
        except ValueError as exc:
            return api_error("validation_error", str(exc), 400)
        return jsonify(payload)


    @app.post(f"{admin_prefix}/api/validate-post")
    @admin_required
    def admin_validate_post():
        payload = request.get_json(silent=True) or {}
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
        raw_post_id = payload.get("post_id")
        try:
            post_id = int(raw_post_id) if raw_post_id else None
        except (TypeError, ValueError):
            return api_error("invalid_post_id", "稿件 ID 无效。", 400)
        result = store.validate_post_for_publish(fields, post_id=post_id)
        return jsonify(result), (200 if result["ok"] else 400)

    @app.get(f"{admin_prefix}/api/posts/<int:post_id>/revisions")
    @admin_required
    def admin_post_revisions(post_id):
        try:
            items = store.list_post_revisions(post_id)
        except ValueError as exc:
            return api_error("post_not_found", str(exc), 404)
        return jsonify({"items": items, "total": len(items)})

    @app.get(f"{admin_prefix}/api/posts/<int:post_id>/revisions/<int:revision_id>")
    @admin_required
    def admin_post_revision_detail(post_id, revision_id):
        revision = store.get_post_revision(post_id, revision_id)
        if revision is None:
            return api_error("revision_not_found", "历史版本不存在。", 404)
        return jsonify(revision)

    @app.post(f"{admin_prefix}/api/posts/<int:post_id>/revisions/<int:revision_id>/restore")
    @admin_required
    def admin_restore_post_revision(post_id, revision_id):
        try:
            post = store.restore_post_revision(post_id, revision_id)
        except ValueError as exc:
            return api_error("revision_restore_failed", str(exc), 400)
        return jsonify({
            "ok": True,
            "post_id": post_id,
            "status": post.get("status", "draft"),
            "updated_at": post.get("updated_at", ""),
            "message": "历史版本已恢复为草稿。",
        })


    def public_base_url() -> str:
        configured = (os.getenv("BLOG_PUBLIC_BASE_URL") or "").strip().rstrip("/")
        if configured:
            return configured
        return request.url_root.rstrip("/")

    def absolute_url(path: str) -> str:
        base = public_base_url()
        if not path:
            return base + "/"
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return base + path

    def atom_datetime(value: str | None) -> str:
        text = (value or "").strip()
        if not text:
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        if "T" in text:
            return text if text.endswith("Z") else text + "Z" if len(text) == 19 else text
        if len(text) >= 10:
            return text[:10] + "T00:00:00Z"
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    def build_atom_feed() -> str:
        base = public_base_url()
        posts = store.list_posts(published_only=True, sort="latest", limit=20)
        updated = atom_datetime(posts[0].get("updated_at") or posts[0].get("published_at") if posts else None)
        entries: list[str] = []
        for post in posts:
            link = absolute_url(f"/posts/{post['slug']}")
            title = xml_escape(str(post.get("title") or ""))
            summary = xml_escape(str(post.get("excerpt") or ""))
            entry_updated = atom_datetime(post.get("updated_at") or post.get("published_at"))
            entries.append(
                "\n".join(
                    [
                        "  <entry>",
                        f"    <title>{title}</title>",
                        f'    <link href="{xml_escape(link)}" rel="alternate" type="text/html"/>',
                        f"    <id>{xml_escape(link)}</id>",
                        f"    <updated>{entry_updated}</updated>",
                        f'    <summary type="text">{summary}</summary>',
                        "  </entry>",
                    ]
                )
            )
        feed = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<feed xmlns="http://www.w3.org/2005/Atom">',
            "  <title>至知</title>",
            "  <subtitle>记录技术实践、项目复盘和长期学习的个人博客</subtitle>",
            f'  <link href="{xml_escape(absolute_url("/feed.xml"))}" rel="self" type="application/atom+xml"/>',
            f'  <link href="{xml_escape(base + "/")}" rel="alternate" type="text/html"/>',
            f"  <id>{xml_escape(base + "/")}</id>",
            f"  <updated>{updated}</updated>",
            *entries,
            "</feed>",
            "",
        ]
        return "\n".join(feed)

    def build_sitemap() -> str:
        posts = store.list_posts(published_only=True, sort="latest")
        urls = [
            ("/", None),
            ("/posts", None),
            ("/about", None),
        ]
        for post in posts:
            lastmod = (post.get("updated_at") or post.get("published_at") or "")[:10] or None
            urls.append((f"/posts/{post['slug']}", lastmod))
        parts = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        ]
        for path, lastmod in urls:
            parts.append("  <url>")
            parts.append(f"    <loc>{xml_escape(absolute_url(path))}</loc>")
            if lastmod:
                parts.append(f"    <lastmod>{xml_escape(lastmod)}</lastmod>")
            parts.append("  </url>")
        parts.append("</urlset>")
        parts.append("")
        return "\n".join(parts)

    _index_html_cache: dict[str, Any] = {"mtime": None, "text": None}

    def load_index_html() -> str | None:
        index_file = FRONTEND_DIST / "index.html"
        if not index_file.exists():
            return None
        mtime = index_file.stat().st_mtime
        if _index_html_cache["mtime"] != mtime or _index_html_cache["text"] is None:
            _index_html_cache["text"] = index_file.read_text(encoding="utf-8")
            _index_html_cache["mtime"] = mtime
        return _index_html_cache["text"]

    def render_spa_index(post: dict[str, Any] | None = None) -> Response | None:
        html_text = load_index_html()
        if html_text is None:
            return None
        if post:
            title = str(post.get("title") or "至知")
            description = str(post.get("excerpt") or "至知：记录技术实践、项目复盘和长期学习的个人博客。")
            page_url = absolute_url(f"/posts/{post['slug']}")
            safe_title = html_lib.escape(title, quote=True)
            safe_desc = html_lib.escape(description, quote=True)
            safe_page_url = html_lib.escape(page_url, quote=True)
            html_text = re.sub(
                r"<title>.*?</title>",
                f"<title>{html_lib.escape(title)} · 至知</title>",
                html_text,
                count=1,
                flags=re.I | re.S,
            )
            desc_pattern = r"<meta[^>]*name=[\"']description[\"'][^>]*/?>"
            if re.search(desc_pattern, html_text, flags=re.I | re.S):
                html_text = re.sub(
                    desc_pattern,
                    f'<meta name="description" content="{safe_desc}" />',
                    html_text,
                    count=1,
                    flags=re.I | re.S,
                )
            else:
                html_text = html_text.replace(
                    "</head>",
                    f'    <meta name="description" content="{safe_desc}" />\n  </head>',
                    1,
                )
            cover = str(post.get("cover_image") or "").strip()
            og_image_tag = ""
            if cover:
                og_image = absolute_url(cover)
                og_image_tag = f'    <meta property="og:image" content="{html_lib.escape(og_image, quote=True)}" />\n'
            og_block = (
                f'    <meta property="og:title" content="{safe_title}" />\n'
                f'    <meta property="og:description" content="{safe_desc}" />\n'
                f'    <meta property="og:type" content="article" />\n'
                f'    <meta property="og:url" content="{safe_page_url}" />\n'
                f"{og_image_tag}"
                f'    <link rel="canonical" href="{safe_page_url}" />\n'
            )
            html_text = html_text.replace("</head>", og_block + "  </head>", 1)
        return Response(html_text, mimetype="text/html; charset=utf-8")

    @app.get("/feed.xml")
    def atom_feed():
        body = build_atom_feed()
        return Response(body, mimetype="application/atom+xml; charset=utf-8")

    @app.get("/sitemap.xml")
    def sitemap_xml():
        body = build_sitemap()
        return Response(body, mimetype="application/xml; charset=utf-8")

    @app.get("/robots.txt")
    def robots_txt():
        body = "User-agent: *\nAllow: /\nSitemap: " + absolute_url("/sitemap.xml") + "\n"
        return Response(body, mimetype="text/plain; charset=utf-8")


    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def frontend(path):
        if path.startswith("api/") or path.startswith("uploads/"):
            abort(404)
        if admin_path and (path == admin_path or path.startswith(f"{admin_path}/")):
            abort(404)

        requested = FRONTEND_DIST / path
        if path and requested.exists() and requested.is_file():
            return send_from_directory(FRONTEND_DIST, path)

        post_for_meta = None
        if path.startswith("posts/"):
            slug = path[len("posts/"):].strip("/")
            if slug and "/" not in slug:
                post_for_meta = store.get_post_by_slug(slug, include_drafts=False)

        spa = render_spa_index(post_for_meta)
        if spa is not None:
            return spa

        return (
            jsonify(
                {
                    "message": (
                        "Vue 前端尚未构建。请先进入 frontend 目录执行 npm install 和 npm run build。"
                    )
                }
            ),
            200,
        )

    app.extensions["blog_login_failures"] = login_failures
    return app


app = create_app()


if __name__ == "__main__":
    debug = env_bool("BLOG_DEBUG", False)
    host = os.getenv("BLOG_HOST", "127.0.0.1")
    port = env_int("BLOG_PORT", 5000, minimum=1)
    app.run(host=host, port=port, debug=debug)



