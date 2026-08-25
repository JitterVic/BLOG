"""序列化器：把内部数据模型裁剪成公开 API / 管理后台的载荷。"""

from __future__ import annotations

from typing import Any


def summarize_post(post) -> dict[str, Any]:
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


def summarize_related_post(post) -> dict[str, Any]:
    return {
        "slug": post["slug"],
        "title": post["title"],
        "excerpt": post["excerpt"],
        "category": post["category"],
    }


def summarize_adjacent_post(post) -> dict[str, Any]:
    return {
        "slug": post["slug"],
        "title": post["title"],
    }


def build_post_detail_payload(post, *, related_posts, previous_post, next_post) -> dict[str, Any]:
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
        "click_count": int(post.get("click_count") or 0),
        "html_content": post.get("html_content") or "",
        "sections": post.get("sections") or [],
        "related_posts": related_posts,
        "previous_post": previous_post,
        "next_post": next_post,
    }


def build_profile_form(profile) -> dict[str, Any]:
    social_links = {item.get("label"): item for item in profile.get("social_links", [])}
    github = social_links.get("GitHub 仓库", {})
    return {
        **profile,
        "github_label": github.get("value", ""),
        "github_url": github.get("url", ""),
        "about_intro_text": "\n".join(profile.get("about_intro", [])),
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


def build_edit_post(post) -> dict[str, Any]:
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

    editable = dict(post)
    tags = editable.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    editable["tags"] = tags
    editable["tags_text"] = ", ".join(tags)
    editable["live_title"] = post.get("title", "")
    editable["live_slug"] = post.get("slug", "")
    if not editable.get("title") and str(editable.get("slug") or "").startswith("draft-"):
        editable["slug"] = ""
    return editable
