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

    def author_attention_items(self, *, limit: int = 8) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for summary in self.posts_repo.list_admin():
            if summary.get("status") == "trashed":
                continue
            post = self.posts_repo.get_by_id(int(summary["id"])) or {}
            fields = self.post_service.snapshot_as_form(post)
            validation = self.post_service.validate_post_for_publish(fields, post_id=int(summary["id"]))
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
                "id": summary["id"],
                "title": summary.get("display_title") or "无标题草稿",
                "status": summary.get("status"),
                "updated_at": summary.get("updated_at"),
                "reasons": reasons,
            })
        return items[:max(1, int(limit))]

    def content_health(self) -> dict[str, Any]:
        active = [item for item in self.posts_repo.list_admin() if item.get("status") != "trashed"]
        without_sections = 0
        missing_images = 0
        empty_alt = 0
        for item in active:
            post = self.posts_repo.get_by_id(int(item["id"])) or {}
            markdown_content = str(post.get("markdown_content") or "")
            if markdown_content and not markdown_has_section_heading(markdown_content):
                without_sections += 1
            for alt, url in markdown_images(markdown_content):
                if not alt or alt.lower() in {"image", "img", "图片"}:
                    empty_alt += 1
                clean_url = unquote(url.split("?", 1)[0].split("#", 1)[0])
                if clean_url.startswith("/uploads/media/"):
                    candidate = uploads.UPLOADS_DIR / "media" / Path(clean_url).name
                    if not candidate.is_file():
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
