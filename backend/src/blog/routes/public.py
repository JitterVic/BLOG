"""公开路由：健康检查、站点资料、文章列表/详情与上传文件访问。"""

from __future__ import annotations

import hashlib

from flask import Blueprint, abort, jsonify, request, send_from_directory, session

from .. import uploads
from ..serializers import (
    build_post_detail_payload,
    summarize_adjacent_post,
    summarize_post,
    summarize_related_post,
)


# The view-dedup marker rides in the same signed cookie as admin_authenticated
# and the CSRF token. Storing raw slugs let a zh-CN slug cost ~99 bytes of JSON
# each (\uXXXX escapes), pushing the cookie past the ~4093-byte browser limit
# after ~26-67 articles — at which point the browser drops the WHOLE cookie and
# silently logs the admin out. Short digests keep the payload bounded instead.
VIEWED_POSTS_MAX = 80
VIEWED_DIGEST_LENGTH = 12

# Longest accepted search/tag filter. Matches the excerpt field limit; well under
# SQLite's LIKE pattern ceiling.
MAX_SEARCH_LENGTH = 1200


def viewed_marker(slug: str) -> str:
    return hashlib.sha256(str(slug).encode("utf-8")).hexdigest()[:VIEWED_DIGEST_LENGTH]


def build_blueprint(store) -> Blueprint:
    bp = Blueprint("public", __name__)

    def healthcheck():
        return jsonify({"status": "ok"})

    def site():
        return jsonify(store.get_site_payload())

    def posts():
        tag = request.args.get("tag")
        category = request.args.get("category")
        limit = request.args.get("limit", type=int)
        sort = request.args.get("sort", "latest")
        # SQLite raises "LIKE or GLOB pattern too complex" near 50k chars, which
        # would surface as an unauthenticated 500. Truncate instead of erroring:
        # no real query is this long, and a prefix still returns sane results.
        q = (request.args.get("q") or "").strip()[:MAX_SEARCH_LENGTH]
        tag = tag[:MAX_SEARCH_LENGTH] if tag else tag
        category = category[:MAX_SEARCH_LENGTH] if category else category
        page = request.args.get("page", type=int)

        list_kwargs = {
            "tag": tag,
            "category": category,
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
            category=category,
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

    def post_detail(slug):
        match = store.get_post_by_slug(slug)
        if match is None:
            abort(404)

        # Count a view once per browser session per slug to avoid double counting
        # when the SPA mounts/remounts the same article during a single session.
        viewed = session.get("viewed_posts") or []
        if not isinstance(viewed, list):
            viewed = []
        marker = viewed_marker(slug)
        if marker not in viewed:
            match["click_count"] = store.increment_post_click(slug)
            viewed = [item for item in viewed if isinstance(item, str)]
            viewed = (viewed + [marker])[-VIEWED_POSTS_MAX:]
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

    def uploads_file(path):
        if not uploads.is_allowed_public_upload_path(path):
            abort(404)

        response = send_from_directory(uploads.UPLOADS_DIR, path)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    bp.add_url_rule("/api/health", "healthcheck", healthcheck, methods=["GET"])
    bp.add_url_rule("/api/site", "site", site, methods=["GET"])
    bp.add_url_rule("/api/posts", "posts", posts, methods=["GET"])
    bp.add_url_rule("/api/posts/<slug>", "post_detail", post_detail, methods=["GET"])
    bp.add_url_rule("/uploads/<path:path>", "uploads", uploads_file, methods=["GET"])
    return bp
