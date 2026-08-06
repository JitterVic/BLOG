"""SPA 托管路由：前端构建产物静态文件与带 SEO meta 的 index 回退。"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, Response, abort, jsonify, send_from_directory

from .. import seo
from ..env_loader import project_root

FRONTEND_DIST = project_root() / "frontend" / "dist"

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
        html_text = seo.inject_post_meta(html_text, post, seo.absolute_url)
    return Response(html_text, mimetype="text/html; charset=utf-8")


def build_blueprint(store, settings) -> Blueprint:
    bp = Blueprint("spa", __name__)
    admin_path = settings.admin_prefix.lstrip("/")

    def frontend(path: str):
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

    bp.add_url_rule("/", "frontend", frontend, methods=["GET"], defaults={"path": ""})
    bp.add_url_rule("/<path:path>", "frontend", frontend, methods=["GET"])
    return bp
