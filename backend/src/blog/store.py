"""兼容门面（facade）：保留原有 ``BlogStore`` API 供既有测试与脚本使用。

新代码请直接使用：

- :mod:`blog.repository` —— SQLite 数据访问
- :mod:`blog.services` —— 业务编排
- :mod:`blog.markdown_tools` / :mod:`blog.uploads` / :mod:`blog.validation` —— 工具层

本模块不再承载实现，仅做委托与重导出。
"""

from __future__ import annotations

import os
from typing import Any

from . import uploads
from .env_loader import env_int
from .markdown_tools import (  # noqa: F401  (兼容重导出)
    build_excerpt as _build_excerpt,
    decode_markdown_file,
    estimate_read_time,
    is_safe_image_url,
    parse_markdown_front_matter,
    render_markdown,
    sanitize_html,
    slugify,
    strip_leading_title_heading,
)
from .repository.database import Database
from .repository.media import MediaRepository
from .repository.posts import PostRepository
from .repository.profile import ProfileRepository
from .repository.revisions import RevisionRepository
from .services.dashboard_service import DashboardService
from .services.import_service import ImportService
from .services.media_service import MediaService
from .services.post_service import PostService, PostVersionConflict
from .services.profile_service import ProfileService
from .uploads import (  # noqa: F401  (兼容重导出)
    DEFAULT_DB_PATH,
    is_allowed_public_upload_path,
    process_uploaded_image_bytes,
    validate_image_upload,
)

__all__ = [
    "BlogStore",
    "DEFAULT_DB_PATH",
    "PostVersionConflict",
    "UPLOADS_DIR",
    "decode_markdown_file",
    "estimate_read_time",
    "is_allowed_public_upload_path",
    "is_safe_image_url",
    "parse_markdown_front_matter",
    "process_uploaded_image_bytes",
    "render_markdown",
    "sanitize_html",
    "slugify",
    "strip_leading_title_heading",
    "validate_image_upload",
]


def __getattr__(name: str):
    # UPLOADS_DIR 委托到 uploads 模块，保证测试对 blog.uploads 的补丁生效。
    if name == "UPLOADS_DIR":
        return uploads.UPLOADS_DIR
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class BlogStore:
    """旧版聚合接口的兼容实现，内部分别委托仓储与服务。"""

    def __init__(self, db_path: str | os.PathLike[str] | None = None):
        self.db = Database(db_path)
        (uploads.UPLOADS_DIR / "media").mkdir(parents=True, exist_ok=True)
        self.max_file_bytes = env_int("BLOG_MAX_UPLOAD_BYTES", 10 * 1024 * 1024, minimum=1)
        self.max_image_bytes = env_int("BLOG_MAX_IMAGE_BYTES", uploads.DEFAULT_MAX_IMAGE_BYTES, minimum=1)
        self.max_image_pixels = env_int("BLOG_MAX_IMAGE_PIXELS", uploads.DEFAULT_MAX_IMAGE_PIXELS, minimum=1)

        self.posts = PostRepository(self.db)
        self.revisions = RevisionRepository(self.db)
        self.profile_repo = ProfileRepository(self.db)
        self.media_repo = MediaRepository(self.db)

        self.post_service = PostService(self.posts, self.revisions)
        self.media_service = MediaService(
            self.media_repo,
            self.posts,
            max_file_bytes=self.max_file_bytes,
            max_image_bytes=self.max_image_bytes,
            max_image_pixels=self.max_image_pixels,
        )
        self.profile_service = ProfileService(self.profile_repo, self.posts)
        self.dashboard_service = DashboardService(self.posts, self.post_service, self.media_service)
        self.import_service = ImportService()

    # ------------------------------------------------------------------
    # 基础设施
    # ------------------------------------------------------------------

    @property
    def db_path(self):
        return self.db.db_path

    def connect(self):
        return self.db.connect()

    def init(self) -> None:
        self.db.init()

    def build_excerpt(self, markdown_content: str) -> str:
        return _build_excerpt(markdown_content)

    def ensure_unique_slug(self, desired_slug: str, *, post_id: int | None = None) -> str:
        return self.posts.ensure_unique_slug(desired_slug, post_id=post_id)

    # ------------------------------------------------------------------
    # 站点资料
    # ------------------------------------------------------------------

    def get_site_profile(self) -> dict[str, Any]:
        return self.profile_service.get_site_profile()

    def get_site_payload(self) -> dict[str, Any]:
        return self.profile_service.get_site_payload()

    def update_site_profile(self, form_data: dict[str, Any]) -> None:
        self.profile_service.update_site_profile(form_data)

    # ------------------------------------------------------------------
    # 文章读取
    # ------------------------------------------------------------------

    def list_posts(self, **kwargs) -> list[dict[str, Any]]:
        return self.posts.list(**kwargs)

    def count_posts(self, **kwargs) -> int:
        return self.posts.count(**kwargs)

    def get_post_by_slug(self, slug: str, *, include_drafts: bool = False) -> dict[str, Any] | None:
        return self.posts.get_by_slug(slug, include_drafts=include_drafts)

    def get_post_by_id(self, post_id: int) -> dict[str, Any] | None:
        return self.posts.get_by_id(post_id)

    def list_admin_posts(self, *, limit: int = 200) -> list[dict[str, Any]]:
        return self.posts.list_admin(limit=limit)

    def get_adjacent_posts(self, post: dict[str, Any]):
        return self.posts.get_adjacent(post)

    def increment_post_click(self, slug: str) -> int:
        return self.posts.increment_click(slug)

    def get_related_posts(
        self,
        post: dict[str, Any],
        *,
        limit: int = 2,
        candidate_limit: int = 48,
    ) -> list[dict[str, Any]]:
        """Pick related published posts without loading full article bodies."""
        slug = str(post.get("slug") or "")
        if not slug or limit <= 0:
            return []

        current_tags = {str(tag).strip().lower() for tag in (post.get("tags") or []) if str(tag).strip()}
        current_category = (post.get("category") or "").strip().lower()
        fetch_limit = max(int(limit), min(int(candidate_limit), 200))
        candidates = self.posts.get_related_candidates(slug, fetch_limit=fetch_limit)

        def related_score(candidate: dict[str, Any]) -> tuple[int, str]:
            candidate_tags = {
                str(tag).strip().lower()
                for tag in (candidate.get("tags") or [])
                if str(tag).strip()
            }
            shared_tags = len(current_tags & candidate_tags)
            same_category = int(
                bool(current_category)
                and (candidate.get("category") or "").strip().lower() == current_category
            )
            return (shared_tags * 3 + same_category * 2, candidate.get("published_at") or "")

        candidates.sort(key=related_score, reverse=True)
        return candidates[:limit]

    def list_taxonomy(self) -> dict[str, list[str]]:
        return self.posts.list_taxonomy()

    # ------------------------------------------------------------------
    # 文章生命周期
    # ------------------------------------------------------------------

    def validate_post_for_publish(self, form_data: dict[str, Any], *, post_id: int | None = None) -> dict[str, Any]:
        return self.post_service.validate_post_for_publish(form_data, post_id=post_id)

    def save_post(self, form_data: dict[str, Any], **kwargs) -> int:
        return self.post_service.save_post(form_data, **kwargs)

    def unpublish_post(self, post_id: int) -> dict[str, Any]:
        return self.post_service.unpublish_post(post_id)

    def trash_post(self, post_id: int) -> None:
        self.post_service.trash_post(post_id)

    def restore_post(self, post_id: int) -> None:
        self.post_service.restore_post(post_id)

    def publish_post(self, post_id: int) -> None:
        self.post_service.publish_post(post_id)

    def purge_post(self, post_id: int) -> None:
        self.post_service.purge_post(post_id)

    def purge_expired_trash(self, *, retention_days: int = 30, now=None) -> int:
        return self.post_service.purge_expired_trash(retention_days=retention_days, now=now)

    # ------------------------------------------------------------------
    # 历史版本
    # ------------------------------------------------------------------

    def create_checkpoint(self, post_id: int) -> int:
        return self.post_service.create_checkpoint(post_id)

    def list_post_revisions(self, post_id: int) -> list[dict[str, Any]]:
        return self.post_service.list_post_revisions(post_id)

    def get_post_revision(self, post_id: int, revision_id: int) -> dict[str, Any] | None:
        return self.post_service.get_post_revision(post_id, revision_id)

    def restore_post_revision(self, post_id: int, revision_id: int) -> dict[str, Any]:
        return self.post_service.restore_post_revision(post_id, revision_id)

    # ------------------------------------------------------------------
    # 媒体与导入
    # ------------------------------------------------------------------

    def list_media_assets(self) -> list[dict[str, Any]]:
        return self.media_service.list_media_assets()

    def save_file(self, file_storage, folder: str, **kwargs) -> str:
        return self.media_service.save_file(file_storage, folder, **kwargs)

    def upload_media(self, file_storage) -> dict[str, str]:
        return self.media_service.upload_media(file_storage)

    def import_markdown(self, file_storage) -> dict[str, Any]:
        return self.import_service.import_markdown(file_storage)

    # ------------------------------------------------------------------
    # 仪表盘
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return self.dashboard_service.stats()

    def content_health(self) -> dict[str, Any]:
        return self.dashboard_service.content_health()

    def author_attention_items(self, *, limit: int = 8) -> list[dict[str, Any]]:
        return self.dashboard_service.author_attention_items(limit=limit)

    def dashboard_overview(self, *, attention_limit: int = 8) -> dict[str, Any]:
        return self.dashboard_service.dashboard_overview(attention_limit=attention_limit)
