"""仪表盘服务：统计、内容健康度与作者待办项。"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .. import uploads
from ..markdown_tools import (
    markdown_has_section_heading,
    markdown_images,
)


class DashboardService:
    def __init__(self, posts_repo, post_service, media_service):
        self.posts_repo = posts_repo
        self.post_service = post_service
        self.media_service = media_service

    def dashboard_overview(self, *, attention_limit: int = 8) -> dict[str, Any]:
        """Health + attention items off ONE post fetch, for the dashboard route."""
        active = self.active_posts()
        return {
            "content_health": self.content_health(active=active),
            "attention_items": self.author_attention_items(limit=attention_limit, active=active),
        }

    def stats(self) -> dict[str, Any]:
        counts = self.posts_repo.count_by_status()
        return {
            "db_path": str(self.posts_repo.db.db_path),
            "post_count": counts["post_count"],
            "published_count": counts["published_count"],
            "draft_count": counts["draft_count"],
            "trashed_count": counts["trashed_count"],
            "upload_dir": str(uploads.UPLOADS_DIR),
        }

    def active_posts(self) -> list[dict[str, Any]]:
        """Non-trashed posts with bodies, fetched in a single query."""
        return [
            item
            for item in self.posts_repo.list_for_dashboard()
            if item.get("status") != "trashed"
        ]

    def author_attention_items(
        self,
        *,
        limit: int = 8,
        active: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for post in active if active is not None else self.active_posts():
            fields = self.post_service.snapshot_as_form(post)
            validation = self.post_service.validate_post_for_publish(fields, post_id=int(post["id"]))
            reasons: list[str] = []
            if not str(post.get("title") or "").strip():
                reasons.append("无标题草稿")
            if validation["errors"]:
                reasons.append(f"{len(validation['errors'])} 个发布错误")
            if validation["warnings"]:
                reasons.append(f"{len(validation['warnings'])} 条发布提醒")
            if not reasons:
                continue
            items.append({
                "id": post["id"],
                "title": post.get("display_title") or "无标题草稿",
                "status": post.get("status"),
                "updated_at": post.get("updated_at"),
                "reasons": reasons,
            })
        return items[:max(1, int(limit))]

    def content_health(self, *, active: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        active = active if active is not None else self.active_posts()
        without_sections = 0
        missing_images = 0
        empty_alt = 0
        # One stat() per distinct media path instead of per reference.
        local_image_exists: dict[str, bool] = {}
        for item in active:
            markdown_content = str(item.get("markdown_content") or "")
            if markdown_content and not markdown_has_section_heading(markdown_content):
                without_sections += 1
            for alt, url in markdown_images(markdown_content):
                if not alt or alt.lower() in {"image", "img", "图片"}:
                    empty_alt += 1
                clean_url = unquote(url.split("?", 1)[0].split("#", 1)[0])
                if clean_url.startswith("/uploads/media/"):
                    exists = local_image_exists.get(clean_url)
                    if exists is None:
                        exists = (uploads.UPLOADS_DIR / "media" / Path(clean_url).name).is_file()
                        local_image_exists[clean_url] = exists
                    if not exists:
                        missing_images += 1
        media_assets = self.media_service.list_media_assets()
        return {
            "missing_cover": sum(1 for item in active if not item.get("cover_image")),
            "missing_taxonomy": sum(1 for item in active if not item.get("category") or not item.get("tags")),
            "missing_sections": without_sections,
            "missing_images": missing_images,
            "empty_image_alt": empty_alt,
            "unreferenced_media": sum(1 for item in media_assets if not item.get("reference_count")),
        }
