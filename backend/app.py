import os
import secrets
import time
from datetime import timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import (
    Flask,
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
    from .env_loader import load_env_file
    from .store import (
        BlogStore,
        PostVersionConflict,
        UPLOADS_DIR,
        estimate_read_time,
        is_allowed_public_upload_path,
        render_markdown,
    )
except ImportError:
    from env_loader import load_env_file
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


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("BLOG_SECRET_KEY", "dev-secret-key-change-me")
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("BLOG_COOKIE_SECURE", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=timedelta(
            seconds=max(300, int(os.getenv("BLOG_SESSION_LIFETIME_SECONDS", str(8 * 60 * 60))))
        ),
        SESSION_REFRESH_EACH_REQUEST=True,
        MAX_CONTENT_LENGTH=int(os.getenv("BLOG_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
    )
    admin_prefix = normalize_admin_prefix(os.getenv("BLOG_ADMIN_PREFIX", "/admin"))
    admin_path = admin_prefix.lstrip("/")
    app.config["ADMIN_PREFIX"] = admin_prefix

    store = BlogStore()
    store.init()
    login_failures: dict[str, list[float]] = {}
    csrf_session_key = "_admin_csrf_token"
    login_window_seconds = max(60, int(os.getenv("BLOG_LOGIN_RATE_WINDOW_SECONDS", "300")))
    login_max_attempts = max(1, int(os.getenv("BLOG_LOGIN_MAX_ATTEMPTS", "5")))

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
        return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",", 1)[0].strip()

    def login_rate_limited() -> tuple[bool, int]:
        now = time.monotonic()
        key = client_key()
        attempts = [stamp for stamp in login_failures.get(key, []) if now - stamp < login_window_seconds]
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
        login_failures[key] = attempts

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
            expected = os.getenv("BLOG_ADMIN_PASSWORD", "admin123456")
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
        return render_template(
            "admin_write.html",
            **build_admin_context(edit_post=build_edit_post(post)),
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
        try:
            saved_id = store.save_post(request.form, post_id=post_id, action=action)
        except ValueError as exc:
            flash(str(exc), "error")
            if post_id:
                return redirect(url_for("admin_write", post_id=post_id))
            return redirect(url_for("admin_write"))

        message = "文章已保存为草稿/已下架。" if action == "draft" else "文章已发布。"
        flash(message, "success")
        return redirect(url_for("admin_write", post_id=saved_id, saved=1))

    @app.post(f"{admin_prefix}/posts/<int:post_id>/delete")
    @admin_required
    def admin_delete_post(post_id):
        try:
            store.delete_post(post_id)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            flash("文章已删除。", "success")
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

        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return send_from_directory(FRONTEND_DIST, "index.html")

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

    return app


app = create_app()


if __name__ == "__main__":
    debug = os.getenv("BLOG_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}
    host = os.getenv("BLOG_HOST", "127.0.0.1")
    port = int(os.getenv("BLOG_PORT", "5000"))
    app.run(host=host, port=port, debug=debug)



