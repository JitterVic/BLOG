"""文章服务：保存/发布/下架/回收/恢复/历史版本等生命周期编排。"""

from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .. import uploads
from ..markdown_tools import (
    build_excerpt,
    estimate_read_time,
    is_safe_image_url,
    markdown_has_heading_space_issue,
    markdown_has_section_heading,
    markdown_has_unclosed_fence,
    markdown_images,
    render_markdown,
    slugify,
)
from ..repository.revisions import POST_EDIT_FIELDS, snapshot_from_row
from ..validation import validate_text_length


class PostVersionConflict(ValueError):
    """Raised when an autosave would overwrite a newer server version."""


class PostService:
    def __init__(self, posts, revisions):
        self.posts = posts
        self.revisions = revisions

    # ------------------------------------------------------------------
    # 快照与表单互转
    # ------------------------------------------------------------------

    @staticmethod
    def snapshot_as_form(snapshot: dict[str, Any]) -> dict[str, Any]:
        result = {field: snapshot.get(field, "") for field in POST_EDIT_FIELDS}
        tags = snapshot.get("tags", [])
        result["tags"] = ", ".join(tags) if isinstance(tags, list) else str(tags or "")
        return result

    def _normalize_edit_snapshot(
        self,
        form_data: dict[str, Any],
        *,
        fallback: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        fallback = fallback or {}
        title = validate_text_length("title", form_data.get("title", fallback.get("title", "")))
        markdown_content = validate_text_length(
            "markdown_content", form_data.get("markdown_content", fallback.get("markdown_content", ""))
        )
        excerpt = validate_text_length("excerpt", form_data.get("excerpt", fallback.get("excerpt", "")))
        read_time = validate_text_length("read_time", form_data.get("read_time", fallback.get("read_time", "")))
        raw_tags = form_data.get("tags", fallback.get("tags", []))
        if isinstance(raw_tags, list):
            tags = [validate_text_length("tag", item, max_length=80) for item in raw_tags if str(item).strip()]
        else:
            tags_text = validate_text_length("tags", raw_tags)
            tags = [validate_text_length("tag", item, max_length=80) for item in tags_text.split(",") if item.strip()]
        if len(tags) > 40:
            raise ValueError("标签数量过多，请控制在 40 个以内。")
        cover_image = validate_text_length(
            "cover_image", form_data.get("cover_image", fallback.get("cover_image", ""))
        )
        if cover_image and not is_safe_image_url(cover_image):
            raise ValueError("封面图片地址无效。")
        return {
            "title": title,
            "slug": validate_text_length("slug", form_data.get("slug", fallback.get("slug", ""))),
            "excerpt": excerpt or build_excerpt(markdown_content),
            "published_at": validate_text_length(
                "published_at", form_data.get("published_at", fallback.get("published_at", ""))
            ),
            "read_time": read_time or estimate_read_time(markdown_content),
            "category": validate_text_length(
                "category", form_data.get("category", fallback.get("category", ""))
            ),
            "tags": tags,
            "hero_quote": validate_text_length(
                "hero_quote", form_data.get("hero_quote", fallback.get("hero_quote", ""))
            ),
            "cover_image": cover_image,
            "markdown_content": markdown_content,
        }

    def _prepare_snapshot_for_post(
        self,
        source: dict[str, Any],
        *,
        fallback: dict[str, Any],
        post_id: int,
        connection=None,
    ) -> dict[str, Any]:
        """Normalize a snapshot and settle its slug.

        Pass *connection* so the slug check runs inside the caller's transaction;
        every caller does, which keeps one transaction model across all write
        paths rather than leaving state transitions on a second connection.
        """
        snapshot = self._normalize_edit_snapshot(source, fallback=fallback)
        desired_slug = snapshot.get("slug") or snapshot.get("title") or fallback.get("slug") or f"draft-{uuid.uuid4().hex[:12]}"
        snapshot["slug"] = self.posts.ensure_unique_slug(
            str(desired_slug), post_id=post_id, connection=connection
        )
        return snapshot

    # ------------------------------------------------------------------
    # 发布校验
    # ------------------------------------------------------------------

    def validate_post_for_publish(
        self,
        form_data: dict[str, Any],
        *,
        post_id: int | None = None,
    ) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []

        def add(target: list[dict[str, str]], code: str, field: str, message: str) -> None:
            target.append({"code": code, "field": field, "message": message})

        try:
            title = validate_text_length("title", form_data.get("title", ""))
            markdown_content = validate_text_length("markdown_content", form_data.get("markdown_content", ""))
            raw_slug = validate_text_length("slug", form_data.get("slug", ""))
            excerpt = validate_text_length("excerpt", form_data.get("excerpt", ""))
            category = validate_text_length("category", form_data.get("category", ""))
            tags_text = validate_text_length("tags", form_data.get("tags", ""))
            cover_image = validate_text_length("cover_image", form_data.get("cover_image", ""))
        except ValueError as exc:
            add(errors, "field_too_long", "", str(exc))
            return {"ok": False, "errors": errors, "warnings": warnings, "normalized": {}}

        tags = [item.strip() for item in tags_text.split(",") if item.strip()]
        if not title:
            add(errors, "title_required", "title", '请先填写文章标题。')
        if not markdown_content:
            add(errors, "content_required", "markdown_content", '发布前请先填写正文。')
        if raw_slug and re.search(r"[\s/?#]", raw_slug):
            add(errors, "invalid_slug", "slug", 'Slug 不能包含空格、斜杠或查询字符。')
        if cover_image and not is_safe_image_url(cover_image):
            add(errors, "invalid_cover", "cover_image", '封面图片必须是 /uploads/ 地址或 http(s) 图片链接。')
        if len(tags) > 40:
            add(errors, "too_many_tags", "tags", '标签数量不能超过 40 个。')
        if any(len(item) > 80 for item in tags):
            add(errors, "tag_too_long", "tags", '单个标签不能超过 80 个字符。')
        if markdown_has_unclosed_fence(markdown_content):
            add(errors, "unclosed_code_fence", "markdown_content", '检测到未闭合的 ``` 代码围栏。')
        if markdown_has_heading_space_issue(markdown_content):
            add(errors, "invalid_heading", "markdown_content", 'Markdown 标题 # 后需要空格。')

        if not excerpt:
            add(warnings, "missing_excerpt", "excerpt", '未填写摘要，发布时将自动生成。')
        if not category:
            add(warnings, "missing_category", "category", '建议填写文章分类，方便前台组织内容。')
        if not tags:
            add(warnings, "missing_tags", "tags", '建议至少填写一个标签。')
        if not cover_image:
            add(warnings, "missing_cover", "cover_image", '未设置封面图，前台将使用文字卡片。')
        if markdown_content and not markdown_has_section_heading(markdown_content):
            add(warnings, "missing_sections", "markdown_content", '正文没有二级标题，前台不会显示目录。')
        if raw_slug and re.search(r"[^\x00-\x7f]", raw_slug):
            add(warnings, "non_ascii_slug", "slug", 'Slug 包含中文或特殊字符，分享链接会被编码。')
        if markdown_content and len(re.sub(r"\s+", "", markdown_content)) < 200:
            add(warnings, "short_content", "markdown_content", '正文较短，请确认内容已经完整。')

        images = markdown_images(markdown_content)
        empty_alt_count = sum(
            1 for alt, _url in images
            if not alt or alt.lower() in {"image", "img", "图片"}
        )
        if empty_alt_count:
            add(warnings, "missing_image_alt", "markdown_content", f"有 {empty_alt_count} 张正文图片缺少有意义的替代文本。")
        missing_local_images = []
        for _alt, url in images:
            clean_url = unquote(url.split("?", 1)[0].split("#", 1)[0])
            if clean_url.startswith("/uploads/media/"):
                candidate = uploads.UPLOADS_DIR / "media" / Path(clean_url).name
                if not candidate.is_file():
                    missing_local_images.append(clean_url)
        if missing_local_images:
            add(errors, "missing_local_image", "markdown_content", f'正文引用了 {len(missing_local_images)} 张不存在的本地图片。')

        normalized_slug = slugify(raw_slug or title) if title or raw_slug else ""
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "normalized": {
                "slug": normalized_slug,
                "excerpt": excerpt or build_excerpt(markdown_content),
                "read_time": estimate_read_time(markdown_content),
            },
        }

    # ------------------------------------------------------------------
    # 保存与状态流转
    # ------------------------------------------------------------------

    def save_post(
        self,
        form_data: dict[str, Any],
        *,
        post_id: int | None = None,
        action: str = "draft",
        expected_updated_at: str | None = None,
        create_revision: bool = True,
        allow_untitled: bool = False,
    ) -> int:
        if action not in {"draft", "published", "update"}:
            raise ValueError('文章状态无效。')
        if action == "published":
            validation = self.validate_post_for_publish(form_data, post_id=post_id)
            if validation["errors"]:
                raise ValueError(validation["errors"][0]["message"])
        if action == "update" and not post_id:
            raise ValueError('只有已存在的文章可以原地更新。')

        title = validate_text_length("title", form_data.get("title", ""))
        if not title and not allow_untitled:
            raise ValueError('文章标题不能为空。')
        markdown_content = validate_text_length("markdown_content", form_data.get("markdown_content", ""))
        html_content = render_markdown(markdown_content)
        excerpt = validate_text_length("excerpt", form_data.get("excerpt", "")) or build_excerpt(markdown_content)
        raw_slug = validate_text_length("slug", form_data.get("slug", ""))
        existing_for_slug = self.posts.get_by_id(post_id) if post_id else None
        if raw_slug:
            desired_slug = raw_slug
        elif existing_for_slug and title and str(existing_for_slug.get("slug") or "").startswith("draft-"):
            desired_slug = title
        elif existing_for_slug:
            desired_slug = existing_for_slug.get("slug") or f"draft-{uuid.uuid4().hex[:12]}"
        elif title:
            desired_slug = title
        else:
            desired_slug = f"draft-{uuid.uuid4().hex[:12]}"
        published = action == "published"
        published_at = validate_text_length("published_at", form_data.get("published_at", ""))
        if published and not published_at:
            published_at = date.today().isoformat()

        tags_text = validate_text_length("tags", form_data.get("tags", ""))
        tags = [validate_text_length("tag", item, max_length=80) for item in tags_text.split(",") if item.strip()]
        if len(tags) > 40:
            raise ValueError('标签数量过多，请控制在 40 个以内。')
        read_time = validate_text_length("read_time", form_data.get("read_time", "")) or estimate_read_time(markdown_content)
        category = validate_text_length("category", form_data.get("category", ""))
        hero_quote = validate_text_length("hero_quote", form_data.get("hero_quote", ""))
        cover_image = validate_text_length("cover_image", form_data.get("cover_image", ""))
        if cover_image and not is_safe_image_url(cover_image):
            raise ValueError('封面图片地址无效：请使用上传得到的 /uploads/ 地址或 http(s) 图片链接。')
        now = datetime.now().isoformat(timespec="microseconds")

        def _attempt() -> int:
            with self.posts.db.connect() as connection:
                # BEGIN IMMEDIATE takes the write lock up front, so the slug
                # uniqueness check below cannot be invalidated by another writer
                # between the SELECT and our INSERT/UPDATE.
                connection.execute("BEGIN IMMEDIATE")
                slug = self.posts.ensure_unique_slug(
                    desired_slug, post_id=post_id, connection=connection
                )
                return self._write_post(
                    connection,
                    post_id=post_id,
                    action=action,
                    slug=slug,
                    title=title,
                    excerpt=excerpt,
                    published=published,
                    published_at=published_at,
                    read_time=read_time,
                    category=category,
                    tags=tags,
                    hero_quote=hero_quote,
                    cover_image=cover_image,
                    markdown_content=markdown_content,
                    html_content=html_content,
                    now=now,
                    expected_updated_at=expected_updated_at,
                    create_revision=create_revision,
                    existing_for_slug=existing_for_slug,
                )

        # Belt and braces: if a concurrent writer still lands the same slug,
        # recompute and retry rather than surfacing a raw IntegrityError as 500.
        for attempt in range(3):
            try:
                return _attempt()
            except sqlite3.IntegrityError:
                if attempt == 2:
                    raise ValueError('保存冲突，请重试一次。') from None
        raise ValueError('保存冲突，请重试一次。')

    def _write_post(
        self,
        connection,
        *,
        post_id: int | None,
        action: str,
        slug: str,
        title: str,
        excerpt: str,
        published: bool,
        published_at: str,
        read_time: str,
        category: str,
        tags: list[str],
        hero_quote: str,
        cover_image: str,
        markdown_content: str,
        html_content: str,
        now: str,
        expected_updated_at: str | None,
        create_revision: bool,
        existing_for_slug: dict[str, Any] | None,
    ) -> int:
        """Single insert/update transaction body, shared by the retry loop."""
        previous_status = ""
        if post_id:
            current_row = connection.execute("SELECT updated_at, status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if current_row is None:
                raise ValueError('稿件不存在。')
            previous_status = current_row["status"] or "draft"
            if action == "published" and previous_status == "published":
                self.revisions.insert_from_row(connection, post_id, "pre_publish")
            if expected_updated_at is not None and current_row["updated_at"] != expected_updated_at:
                raise PostVersionConflict('文章已在其他页面更新，请重新加载后再保存。')
            if action == "update":
                status = previous_status
                if not published_at:
                    published_at = existing_for_slug.get("published_at", "") if existing_for_slug else ""
            else:
                status = "published" if published else "draft"
            self.posts.update_full(
                post_id,
                slug=slug,
                title=title,
                excerpt=excerpt,
                published_at=published_at,
                read_time=read_time,
                category=category,
                tags=tags,
                hero_quote=hero_quote,
                cover_image=cover_image,
                markdown_content=markdown_content,
                html_content=html_content,
                status=status,
                updated_at=now,
                connection=connection,
            )
            saved_id = post_id
        else:
            status = "published" if published else "draft"
            saved_id = self.posts.insert_full(
                slug=slug,
                title=title,
                excerpt=excerpt,
                published_at=published_at,
                read_time=read_time,
                category=category,
                tags=tags,
                hero_quote=hero_quote,
                cover_image=cover_image,
                markdown_content=markdown_content,
                html_content=html_content,
                status=status,
                now=now,
                connection=connection,
            )

        if create_revision:
            if not post_id:
                revision_type = "created"
            elif action == "published":
                revision_type = "published"
            elif previous_status == "published":
                revision_type = "unpublished"
            else:
                revision_type = "draft_saved"
            self.revisions.insert_from_row(connection, saved_id, revision_type)
        connection.commit()
        return saved_id

    def unpublish_post(self, post_id: int) -> dict[str, Any]:
        post = self.posts.get_by_id(post_id)
        if post is None:
            raise ValueError("文章不存在。")
        if post.get("status") != "published":
            raise ValueError("只有已发布文章可以下架。")
        now = datetime.now().isoformat(timespec="microseconds")
        with self.posts.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if current is None or current["status"] != "published":
                raise PostVersionConflict("文章状态已变化，请重新加载。")
            snapshot = self._prepare_snapshot_for_post(
                post, fallback=post, post_id=post_id, connection=connection
            )
            self.revisions.insert_from_row(connection, post_id, "pre_unpublish")
            self.posts.update_from_snapshot(
                post_id, snapshot, status="draft", updated_at=now, deleted_at=None, connection=connection
            )
            self.revisions.insert_from_row(connection, post_id, "unpublished")
            connection.commit()
        return self.posts.get_by_id(post_id) or {}

    def trash_post(self, post_id: int) -> None:
        post = self.posts.get_by_id(post_id)
        if post is None:
            raise ValueError("文章不存在或已经被删除。")
        if post.get("status") == "trashed":
            raise ValueError("文章已经在回收站中。")
        now = datetime.now().isoformat(timespec="microseconds")
        with self.posts.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if current is None or current["status"] == "trashed":
                raise PostVersionConflict("文章状态已变化，请重新加载。")
            snapshot = self._prepare_snapshot_for_post(
                post, fallback=post, post_id=post_id, connection=connection
            )
            self.revisions.insert_from_row(connection, post_id, "pre_trash")
            self.posts.update_from_snapshot(
                post_id, snapshot, status="trashed", updated_at=now, deleted_at=now, connection=connection
            )
            self.revisions.insert_from_row(connection, post_id, "trashed")
            connection.commit()

    def restore_post(self, post_id: int) -> None:
        now = datetime.now().isoformat(timespec="microseconds")
        with self.posts.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                raise ValueError('文章不存在。')
            if row["status"] != "trashed":
                raise ValueError('只有回收站中的文章可以恢复。')
            connection.execute(
                "UPDATE posts SET status = 'draft', deleted_at = NULL, updated_at = ? WHERE id = ?",
                (now, post_id),
            )
            self.revisions.insert_from_row(connection, post_id, "restored_from_trash")
            connection.commit()

    def publish_post(self, post_id: int) -> None:
        """Quick-publish a draft from the post list after full publish checks."""
        post = self.posts.get_by_id(post_id)
        if post is None:
            raise ValueError('文章不存在。')
        if post.get("status") == "trashed":
            raise ValueError('回收站文章不能发布，请先恢复为草稿。')
        if post.get("status") == "published":
            raise ValueError('文章已经处于发布状态。')
        form_data = {
            "title": post.get("title", ""),
            "markdown_content": post.get("markdown_content", ""),
            "slug": post.get("slug", ""),
            "excerpt": post.get("excerpt", ""),
            "category": post.get("category", ""),
            "tags": ", ".join(post.get("tags") or []),
            "cover_image": post.get("cover_image", ""),
            "published_at": post.get("published_at", ""),
        }
        result = self.validate_post_for_publish(form_data, post_id=post_id)
        if not result["ok"]:
            first_error = result["errors"][0]["message"] if result["errors"] else '发布校验未通过。'
            raise ValueError(f'无法发布：{first_error}')
        now = datetime.now().isoformat(timespec="microseconds")
        published_at = post.get("published_at") or date.today().isoformat()
        with self.posts.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if current is None:
                raise ValueError('文章不存在。')
            if current["status"] == "published":
                raise ValueError('文章已经处于发布状态。')
            connection.execute(
                "UPDATE posts SET status = 'published', published_at = ?, updated_at = ?, deleted_at = NULL WHERE id = ?",
                (published_at, now, post_id),
            )
            self.revisions.insert_from_row(connection, post_id, "published")
            connection.commit()

    def purge_post(self, post_id: int) -> None:
        """Permanently delete a trashed post (revisions cascade-delete)."""
        with self.posts.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                raise ValueError('文章不存在。')
            if row["status"] != "trashed":
                raise ValueError('只有回收站中的文章可以彻底删除。')
            connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            connection.commit()

    def purge_expired_trash(self, *, retention_days: int = 30, now: datetime | None = None) -> int:
        return self.posts.purge_expired_trash(retention_days=retention_days, now=now)

    # ------------------------------------------------------------------
    # 历史版本
    # ------------------------------------------------------------------

    def create_checkpoint(self, post_id: int) -> int:
        with self.posts.db.connect() as connection:
            row = connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                raise ValueError("稿件不存在。")
            snapshot = snapshot_from_row(row)
            revision_id = self.revisions.insert_snapshot(connection, post_id, "checkpoint", snapshot)
            connection.commit()
        return revision_id

    def list_post_revisions(self, post_id: int) -> list[dict[str, Any]]:
        if self.posts.get_by_id(post_id) is None:
            raise ValueError('稿件不存在。')
        return self.revisions.list(post_id)

    def get_post_revision(self, post_id: int, revision_id: int) -> dict[str, Any] | None:
        revision = self.revisions.get(post_id, revision_id)
        if revision is None:
            return None
        snapshot = revision["snapshot"]
        markdown_content = str(snapshot.get("markdown_content") or "")
        snapshot["html_content"] = render_markdown(markdown_content)
        return revision

    def restore_post_revision(self, post_id: int, revision_id: int) -> dict[str, Any]:
        revision = self.get_post_revision(post_id, revision_id)
        if revision is None:
            raise ValueError('历史版本不存在。')
        snapshot = revision["snapshot"]
        title = validate_text_length("title", snapshot.get("title", ""))
        validate_text_length("markdown_content", snapshot.get("markdown_content", ""))
        if not title:
            raise ValueError('历史版本缺少文章标题，无法恢复。')
        current_post = self.posts.get_by_id(post_id)
        if current_post is None:
            raise ValueError("稿件不存在。")
        status = "published" if current_post.get("status") == "published" else "draft"
        now = datetime.now().isoformat(timespec="microseconds")
        with self.posts.db.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
            if current is None:
                raise ValueError('稿件不存在。')
            # Restore must not resurrect a slug now owned by another post (slug is UNIQUE).
            restored = self._prepare_snapshot_for_post(
                snapshot, fallback=current_post, post_id=post_id, connection=connection
            )
            cover_image = restored.get("cover_image", "")
            if cover_image and not is_safe_image_url(cover_image):
                restored["cover_image"] = ""
            self.revisions.insert_from_row(connection, post_id, "pre_restore")
            self.posts.update_from_snapshot(
                post_id, restored, status=status, updated_at=now, deleted_at=None, connection=connection
            )
            self.revisions.insert_from_row(connection, post_id, "restored")
            connection.commit()
        return self.posts.get_by_id(post_id) or {}
