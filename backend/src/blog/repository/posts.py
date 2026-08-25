"""文章仓储：posts 表的查询、写入与状态更新（不含发布/回收等业务编排）。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from ..markdown_tools import estimate_read_time, render_markdown, slugify

JSON_FIELDS = {
    "social_links",
    "about_intro",
    "tags",
    "sections",
}

# Compact columns for list/related responses. Keep detail queries on SELECT *
# so markdown/html only load when a single post is opened.
LIST_POST_COLUMNS = (
    "id, slug, title, excerpt, published_at, created_at, updated_at, "
    "read_time, category, tags, hero_quote, cover_image, "
    "status, click_count, deleted_at"
)
ADMIN_LIST_LIMIT = 200


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    for field in JSON_FIELDS:
        if field in data:
            data[field] = json.loads(data[field] or "[]")
    if "html_content" in data:
        data["html_content"] = data.get("html_content") or (
            render_markdown(data.get("markdown_content", ""))
            if data.get("markdown_content")
            else ""
        )
    # List queries intentionally omit body columns; keep keys absent rather
    # than inventing empty markdown/html fields.
    return data


class PostRepository:
    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def get_raw_row(self, post_id: int) -> sqlite3.Row | None:
        with self.db.connect() as connection:
            return connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()

    def get_by_id(self, post_id: int) -> dict[str, Any] | None:
        return row_to_dict(self.get_raw_row(post_id))

    def get_by_slug(self, slug: str, *, include_drafts: bool = False) -> dict[str, Any] | None:
        query = "SELECT * FROM posts WHERE slug = ?"
        params: list[Any] = [slug]
        if not include_drafts:
            query += " AND status = 'published'"

        with self.db.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return row_to_dict(row)

    def build_filters(
        self,
        *,
        tag: str | None = None,
        published_only: bool = True,
        search: str | None = None,
    ) -> tuple[str, list[Any]]:
        conditions = []
        params: list[Any] = []

        if published_only:
            conditions.append("status = 'published'")
        if search and search.strip():
            pattern = f"%{_escape_like(search.strip().lower())}%"
            conditions.append(
                r"(LOWER(title) LIKE ? ESCAPE '\'"
                r" OR LOWER(excerpt) LIKE ? ESCAPE '\'"
                r" OR LOWER(tags) LIKE ? ESCAPE '\'"
                r" OR LOWER(markdown_content) LIKE ? ESCAPE '\')"
            )
            params.extend([pattern, pattern, pattern, pattern])
        if tag and tag.strip():
            serialized_tag = json.dumps(tag.strip().lower(), ensure_ascii=False)
            conditions.append(r"LOWER(tags) LIKE ? ESCAPE '\'")
            params.append(f"%{_escape_like(serialized_tag)}%")

        where_sql = " WHERE " + " AND ".join(conditions) if conditions else ""
        return where_sql, params

    @staticmethod
    def order_clause(sort: str = "latest") -> str:
        if sort == "hot":
            return " ORDER BY click_count DESC, published_at DESC, updated_at DESC, id DESC"
        return " ORDER BY published_at DESC, updated_at DESC, id DESC"

    def count(
        self,
        *,
        tag: str | None = None,
        published_only: bool = True,
        search: str | None = None,
    ) -> int:
        where_sql, params = self.build_filters(tag=tag, published_only=published_only, search=search)
        with self.db.connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM posts{where_sql}", params).fetchone()
        return int(row[0] if row else 0)

    def list(
        self,
        *,
        tag: str | None = None,
        published_only: bool = True,
        sort: str = "latest",
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = self.build_filters(tag=tag, published_only=published_only, search=search)
        query = f"SELECT {LIST_POST_COLUMNS} FROM posts{where_sql}{self.order_clause(sort)}"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
            if offset is not None:
                query += " OFFSET ?"
                params.append(max(0, int(offset)))
        elif offset is not None:
            query += " LIMIT -1 OFFSET ?"
            params.append(max(0, int(offset)))

        with self.db.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [row_to_dict(row) for row in rows]

    def list_admin(self, *, limit: int = ADMIN_LIST_LIMIT) -> list[dict[str, Any]]:
        capped = max(1, min(int(limit or ADMIN_LIST_LIMIT), ADMIN_LIST_LIMIT))
        with self.db.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT {LIST_POST_COLUMNS}
                FROM posts
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (capped,),
            ).fetchall()
        items = [row_to_dict(row) for row in rows]
        for item in items:
            item["display_title"] = item.get("title") or "\u65e0\u6807\u9898\u8349\u7a3f"
        return items[:capped]

    def get_adjacent(self, post: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        current = (
            post.get("published_at") or "",
            post.get("updated_at") or "",
            int(post.get("id") or 0),
        )

        with self.db.connect() as connection:
            previous_row = connection.execute(
                """
                SELECT * FROM posts
                WHERE status = 'published'
                  AND (published_at, updated_at, id) < (?, ?, ?)
                ORDER BY published_at DESC, updated_at DESC, id DESC
                LIMIT 1
                """,
                current,
            ).fetchone()
            next_row = connection.execute(
                """
                SELECT * FROM posts
                WHERE status = 'published'
                  AND (published_at, updated_at, id) > (?, ?, ?)
                ORDER BY published_at ASC, updated_at ASC, id ASC
                LIMIT 1
                """,
                current,
            ).fetchone()

        return row_to_dict(previous_row), row_to_dict(next_row)

    def get_related_candidates(
        self,
        slug: str,
        *,
        fetch_limit: int,
    ) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, slug, title, excerpt, category, tags, published_at, updated_at, click_count
                FROM posts
                WHERE status = 'published' AND slug != ?
                ORDER BY published_at DESC, updated_at DESC, id DESC
                LIMIT ?
                """,
                (slug, fetch_limit),
            ).fetchall()
        return [row_to_dict(row) for row in rows]

    def increment_click(self, slug: str) -> int:
        """Increase public view count once. Returns the updated click_count (or current if missing)."""
        with self.db.connect() as connection:
            # SQLite 3.35+ supports RETURNING; fall back for older builds.
            try:
                row = connection.execute(
                    """
                    UPDATE posts
                    SET click_count = COALESCE(click_count, 0) + 1
                    WHERE slug = ? AND status = 'published'
                    RETURNING click_count
                    """,
                    (slug,),
                ).fetchone()
            except sqlite3.OperationalError:
                connection.execute(
                    """
                    UPDATE posts
                    SET click_count = COALESCE(click_count, 0) + 1
                    WHERE slug = ? AND status = 'published'
                    """,
                    (slug,),
                )
                row = connection.execute(
                    "SELECT click_count FROM posts WHERE slug = ? AND status = 'published'",
                    (slug,),
                ).fetchone()
            connection.commit()
        return int(row["click_count"] if row else 0)

    def ensure_unique_slug(
        self,
        desired_slug: str,
        *,
        post_id: int | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> str:
        """Pick a free slug. Pass *connection* so the check and the following
        write share one transaction — otherwise two concurrent saves can both
        clear the check and the loser dies on the UNIQUE constraint."""
        base_slug = slugify(desired_slug)

        def _execute(conn: sqlite3.Connection) -> str:
            candidate = base_slug
            counter = 2
            while True:
                row = conn.execute(
                    "SELECT id FROM posts WHERE slug = ?",
                    (candidate,),
                ).fetchone()
                if row is None or (post_id and row["id"] == post_id):
                    return candidate
                candidate = f"{base_slug}-{counter}"
                counter += 1

        if connection is not None:
            return _execute(connection)
        with self.db.connect() as conn:
            return _execute(conn)

    def scan_rows(self) -> list[sqlite3.Row]:
        """素材引用扫描所需的轻量行集合。"""
        with self.db.connect() as connection:
            return connection.execute(
                "SELECT id, title, slug, status, cover_image, markdown_content FROM posts"
            ).fetchall()

    def list_for_dashboard(self, *, limit: int = ADMIN_LIST_LIMIT) -> list[dict[str, Any]]:
        """Dashboard rows including bodies, in ONE query.

        The dashboard needs markdown_content for every active post. Fetching it
        per post via get_by_id cost one connection each (300+ per render at 150
        posts), so select the whole working set at once instead.
        """
        capped = max(1, min(int(limit or ADMIN_LIST_LIMIT), ADMIN_LIST_LIMIT))
        with self.db.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT {LIST_POST_COLUMNS}, markdown_content
                FROM posts
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (capped,),
            ).fetchall()
        items = [row_to_dict(row) for row in rows]
        for item in items:
            item["display_title"] = item.get("title") or "无标题草稿"
        return items

    def published_tags(self) -> set[str]:
        tags: set[str] = set()
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT tags FROM posts WHERE status = 'published'"
            ).fetchall()
        for row in rows:
            try:
                values = json.loads(row["tags"] or "[]")
            except (TypeError, json.JSONDecodeError):
                values = []
            if isinstance(values, list):
                tags.update(str(tag).strip() for tag in values if str(tag).strip())
        return tags

    def list_taxonomy(self) -> dict[str, list[str]]:
        with self.db.connect() as connection:
            rows = connection.execute("SELECT category, tags FROM posts WHERE status != 'trashed'").fetchall()
        categories: set[str] = set()
        tags: set[str] = set()
        for row in rows:
            category = str(row["category"] or "").strip()
            if category:
                categories.add(category)
            try:
                values = json.loads(row["tags"] or "[]")
            except (TypeError, json.JSONDecodeError):
                values = []
            tags.update(str(item).strip() for item in values if str(item).strip())
        return {"categories": sorted(categories), "tags": sorted(tags)}

    def count_by_status(self) -> dict[str, int]:
        with self.db.connect() as connection:
            post_count = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            draft_count = connection.execute("SELECT COUNT(*) FROM posts WHERE status = 'draft'").fetchone()[0]
            published_count = connection.execute("SELECT COUNT(*) FROM posts WHERE status = 'published'").fetchone()[0]
            trashed_count = connection.execute("SELECT COUNT(*) FROM posts WHERE status = 'trashed'").fetchone()[0]
        return {
            "post_count": int(post_count),
            "published_count": int(published_count),
            "draft_count": int(draft_count),
            "trashed_count": int(trashed_count),
        }

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def insert_full(
        self,
        *,
        slug: str,
        title: str,
        excerpt: str,
        published_at: str,
        read_time: str,
        category: str,
        tags: list[str],
        hero_quote: str,
        cover_image: str,
        markdown_content: str,
        html_content: str,
        status: str,
        now: str,
        connection: sqlite3.Connection | None = None,
    ) -> int:
        tags_json = json.dumps(tags, ensure_ascii=False)
        sections = json.dumps([], ensure_ascii=False)

        def _execute(connection: sqlite3.Connection) -> int:
            connection.execute(
                """
                INSERT INTO posts (
                    slug, title, excerpt, published_at, created_at, updated_at,
                    read_time, category, tags, hero_quote,
                    cover_image, sections, markdown_content, html_content, status, deleted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (slug, title, excerpt, published_at, now, now, read_time, category, tags_json,
                 hero_quote, cover_image, sections, markdown_content, html_content, status),
            )
            return int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

        if connection is not None:
            return _execute(connection)
        with self.db.connect() as connection:
            saved_id = _execute(connection)
            connection.commit()
        return saved_id

    def update_full(
        self,
        post_id: int,
        *,
        slug: str,
        title: str,
        excerpt: str,
        published_at: str,
        read_time: str,
        category: str,
        tags: list[str],
        hero_quote: str,
        cover_image: str,
        markdown_content: str,
        html_content: str,
        status: str,
        updated_at: str,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        tags_json = json.dumps(tags, ensure_ascii=False)
        sections = json.dumps([], ensure_ascii=False)

        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                UPDATE posts
                SET slug = ?, title = ?, excerpt = ?, published_at = ?, updated_at = ?,
                    read_time = ?, category = ?, tags = ?,
                    hero_quote = ?, cover_image = ?, sections = ?, markdown_content = ?,
                    html_content = ?, status = ?, deleted_at = NULL
                WHERE id = ?
                """,
                (slug, title, excerpt, published_at, updated_at, read_time, category, tags_json,
                 hero_quote, cover_image, sections, markdown_content, html_content, status, post_id),
            )

        if connection is not None:
            _execute(connection)
            return
        with self.db.connect() as conn:
            _execute(conn)
            conn.commit()

    def update_from_snapshot(
        self,
        post_id: int,
        snapshot: dict[str, Any],
        *,
        status: str,
        updated_at: str,
        deleted_at: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        tags = snapshot.get("tags") if isinstance(snapshot.get("tags"), list) else []
        markdown_content = str(snapshot.get("markdown_content") or "")

        def _execute(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                UPDATE posts
                SET title = ?, slug = ?, excerpt = ?, published_at = ?, read_time = ?,
                    category = ?, tags = ?, hero_quote = ?, cover_image = ?,
                    markdown_content = ?, html_content = ?, status = ?, deleted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    snapshot.get("title", ""),
                    snapshot.get("slug", ""),
                    snapshot.get("excerpt", ""),
                    snapshot.get("published_at", ""),
                    snapshot.get("read_time", "") or estimate_read_time(markdown_content),
                    snapshot.get("category", ""),
                    json.dumps(tags, ensure_ascii=False),
                    snapshot.get("hero_quote", ""),
                    snapshot.get("cover_image", ""),
                    markdown_content,
                    render_markdown(markdown_content),
                    status,
                    deleted_at,
                    updated_at,
                    post_id,
                ),
            )

        if connection is not None:
            _execute(connection)
            return
        with self.db.connect() as conn:
            _execute(conn)
            conn.commit()

    def purge_expired_trash(self, *, retention_days: int = 30, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now()) - timedelta(days=max(1, retention_days))
        with self.db.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM posts WHERE status = 'trashed' AND deleted_at IS NOT NULL AND deleted_at <= ?",
                (cutoff.isoformat(timespec="microseconds"),),
            )
            connection.commit()
        return max(0, int(cursor.rowcount or 0))
