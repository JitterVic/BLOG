import os
import secrets
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

from env_loader import load_env_file
from store import BlogStore, UPLOADS_DIR, estimate_read_time, is_allowed_public_upload_path, render_markdown


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
            "featured": False,
            "tone": "amber",
            "tags_text": "",
            "hero_quote": "",
            "cover_image": "",
            "markdown_content": "",
            "html_content": "",
            "status": "draft",
        }

    return {
        **post,
        "featured": bool(post.get("featured")),
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
        MAX_CONTENT_LENGTH=int(os.getenv("BLOG_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
    )
    admin_prefix = normalize_admin_prefix(os.getenv("BLOG_ADMIN_PREFIX", "/admin"))
    admin_path = admin_prefix.lstrip("/")
    app.config["ADMIN_PREFIX"] = admin_prefix

    store = BlogStore()
    store.init()

    def is_authenticated():
        return session.get("admin_authenticated") is True

    def admin_required(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not is_authenticated():
                return redirect(url_for("admin_login", next=request.path))
            return view_func(*args, **kwargs)

        return wrapped

    @app.get("/api/health")
    def healthcheck():
        return jsonify({"status": "ok", "database": str(store.db_path)})

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

        store.increment_post_click(slug)
        match["click_count"] = int(match.get("click_count") or 0) + 1

        previous_match, next_match = store.get_adjacent_posts(match)
        previous_post = summarize_adjacent_post(previous_match) if previous_match else None
        next_post = summarize_adjacent_post(next_match) if next_match else None

        published_posts = store.list_posts(published_only=True)
        current_tags = {tag.lower() for tag in match.get("tags", [])}
        current_category = (match.get("category") or "").strip().lower()

        def related_score(candidate):
            candidate_tags = {tag.lower() for tag in candidate.get("tags", [])}
            shared_tags = len(current_tags & candidate_tags)
            same_category = int(
                bool(current_category)
                and (candidate.get("category") or "").strip().lower() == current_category
            )
            return shared_tags * 3 + same_category * 2

        related_candidates = [post for post in published_posts if post["slug"] != slug]
        related_candidates.sort(
            key=lambda post: (related_score(post), post.get("published_at", "")),
            reverse=True,
        )
        related_posts = [summarize_related_post(post) for post in related_candidates[:2]]

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
            password = request.form.get("password", "")
            expected = os.getenv("BLOG_ADMIN_PASSWORD", "admin123456")
            if secrets.compare_digest(password, expected):
                session.clear()
                session["admin_authenticated"] = True
                flash("已进入管理后台。", "success")
                next_target = request.args.get("next")
                if not is_safe_admin_next(next_target, admin_prefix):
                    next_target = url_for("admin_dashboard")
                return redirect(next_target)

            flash("密码错误，请重试。", "error")

        return render_template("admin_login.html")

    @app.get(f"{admin_prefix}/logout")
    def admin_logout():
        session.clear()
        flash("你已退出后台。", "success")
        return redirect(url_for("admin_login"))

    @app.get(admin_prefix)
    @admin_required
    def admin_dashboard():
        selected_post_id = request.args.get("post_id", type=int)
        edit_post = build_edit_post(store.get_post_by_id(selected_post_id) if selected_post_id else None)
        profile = store.get_site_profile()
        stats = store.stats()
        stats["admin_prefix"] = admin_prefix
        return render_template(
            "admin_dashboard.html",
            profile_form=build_profile_form(profile),
            profile=profile,
            admin_posts=store.list_admin_posts(),
            edit_post=edit_post,
            stats=stats,
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
        return redirect(url_for("admin_dashboard"))

    @app.post(f"{admin_prefix}/posts/save")
    @admin_required
    def admin_save_post():
        post_id = request.form.get("post_id", type=int)
        action = request.form.get("action", "draft")
        try:
            saved_id = store.save_post(request.form, post_id=post_id, action=action)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_dashboard", post_id=post_id) if post_id else url_for("admin_dashboard"))

        flash("文章已保存为草稿/已下架。" if action == "draft" else "文章已发布。", "success")
        return redirect(url_for("admin_dashboard", post_id=saved_id))

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

    @app.post(f"{admin_prefix}/api/preview-markdown")
    @admin_required
    def admin_preview_markdown():
        payload = request.get_json(silent=True) or {}
        markdown_content = payload.get("markdown_content", "")
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
            return jsonify({"message": "请选择一个 Markdown 文件。"}), 400
        try:
            payload = store.import_markdown(markdown_file)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        return jsonify(payload)

    @app.post(f"{admin_prefix}/api/upload-image")
    @admin_required
    def admin_upload_image():
        image_file = request.files.get("image")
        if image_file is None or not image_file.filename:
            return jsonify({"message": "请选择一张图片。"}), 400
        try:
            payload = store.upload_media(image_file)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
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



