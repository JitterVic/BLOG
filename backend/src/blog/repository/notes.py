"""余笺仓储：独立 notes 表的查询与写入。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from ..markdown_tools import render_markdown

NOTE_TYPES = ("daily", "project", "work", "thought")
NOTE_TYPE_LABELS = {
    "daily": "日常",
    "project": "项目",
    "work": "作品",
    "thought": "随想",
}

LIST_NOTE_COLUMNS = (
    "id, slug, title, type, excerpt, published_at, created_at, updated_at, "
    "media, external_url, status, deleted_at"
)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    result = dict(row)
    try:
        result["media"] = json.loads(result.get("media") or "[]")
    except (TypeError, json.JSONDecodeError):
        result["media"] = []
    if "html_content" in result:
        result["html_content"] = result.get("html_content") or render_markdown(
            result.get("markdown_content") or ""
        )
    return result


class NoteRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, note_id: int) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return row_to_dict(row)

    def get_by_slug(self, slug: str, *, include_drafts: bool = False) -> dict[str, Any] | None:
        query = "SELECT * FROM notes WHERE slug = ?"
        params: list[Any] = [slug]
        if not include_drafts:
            query += " AND status = 'published' AND deleted_at IS NULL"
        with self.db.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return row_to_dict(row)

    def count(self, *, note_type: str | None = None, published_only: bool = True) -> int:
        where, params = self._filters(note_type=note_type, published_only=published_only)
        with self.db.connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM notes{where}", params).fetchone()
        return int(row[0] if row else 0)

    def list(
        self,
        *,
        note_type: str | None = None,
        published_only: bool = True,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        where, params = self._filters(note_type=note_type, published_only=published_only)
        query = f"SELECT {LIST_NOTE_COLUMNS} FROM notes{where} ORDER BY published_at DESC, updated_at DESC, id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
            if offset is not None:
                query += " OFFSET ?"
                params.append(max(0, int(offset)))
        with self.db.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [row_to_dict(row) for row in rows]

    def _filters(self, *, note_type: str | None, published_only: bool) -> tuple[str, list[Any]]:
        conditions = []
        params: list[Any] = []
        if published_only:
            conditions.extend(["status = 'published'", "deleted_at IS NULL"])
        if note_type:
            conditions.append("type = ?")
            params.append(note_type)
        return (" WHERE " + " AND ".join(conditions)) if conditions else "", params

    def ensure_unique_slug(self, desired_slug: str, *, note_id: int | None = None) -> str:
        base = desired_slug.strip() or "note"
        candidate = base
        suffix = 2
        with self.db.connect() as connection:
            while True:
                row = connection.execute("SELECT id FROM notes WHERE slug = ?", (candidate,)).fetchone()
                if row is None or int(row[0]) == note_id:
                    return candidate
                candidate = f"{base}-{suffix}"
                suffix += 1

    def save(self, data: dict[str, Any], *, note_id: int | None = None) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        fields = (
            data["slug"], data["title"], data["type"], data.get("excerpt", ""),
            data.get("published_at", ""), now, now, json.dumps(data.get("media", []), ensure_ascii=False),
            data.get("external_url", ""), data.get("markdown_content", ""), data.get("html_content", ""),
            data.get("status", "draft"),
        )
        with self.db.connect() as connection:
            if note_id:
                connection.execute(
                    """UPDATE notes SET slug=?, title=?, type=?, excerpt=?, published_at=?, updated_at=?,
                    media=?, external_url=?, markdown_content=?, html_content=?, status=?, deleted_at=NULL
                    WHERE id=?""",
                    (fields[0], fields[1], fields[2], fields[3], fields[4], fields[6], *fields[7:], note_id),
                )
                saved_id = note_id
            else:
                cursor = connection.execute(
                    """INSERT INTO notes
                    (slug, title, type, excerpt, published_at, created_at, updated_at, media,
                     external_url, markdown_content, html_content, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    fields,
                )
                saved_id = int(cursor.lastrowid)
            connection.commit()
        return saved_id