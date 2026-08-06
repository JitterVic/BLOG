"""历史版本仓储：post_revisions 表的快照读写。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

MAX_REVISIONS_PER_POST = 50
POST_REVISION_FIELDS = (
    "title", "slug", "excerpt", "published_at", "read_time", "category",
    "tags", "hero_quote", "cover_image", "markdown_content",
    "html_content", "status",
)
POST_EDIT_FIELDS = (
    "title", "slug", "excerpt", "published_at", "read_time", "category",
    "tags", "hero_quote", "cover_image", "markdown_content",
)


def snapshot_from_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    source = dict(row)
    snapshot: dict[str, Any] = {}
    for field in POST_REVISION_FIELDS:
        value = source.get(field, "")
        if field == "tags" and not isinstance(value, list):
            try:
                value = json.loads(value or "[]")
            except (TypeError, json.JSONDecodeError):
                value = []
        snapshot[field] = value
    return snapshot


class RevisionRepository:
    def __init__(self, db):
        self.db = db

    def insert_snapshot(
        self,
        connection: sqlite3.Connection,
        post_id: int,
        revision_type: str,
        snapshot: dict[str, Any],
    ) -> int:
        created_at = datetime.now().isoformat(timespec="microseconds")
        cursor = connection.execute(
            """
            INSERT INTO post_revisions (post_id, revision_type, snapshot_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (post_id, revision_type, json.dumps(snapshot, ensure_ascii=False), created_at),
        )
        connection.execute(
            """
            DELETE FROM post_revisions
            WHERE post_id = ? AND id NOT IN (
                SELECT id FROM post_revisions
                WHERE post_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
            )
            """,
            (post_id, post_id, MAX_REVISIONS_PER_POST),
        )
        return int(cursor.lastrowid)

    def insert_from_row(
        self,
        connection: sqlite3.Connection,
        post_id: int,
        revision_type: str,
    ) -> int:
        row = connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if row is None:
            raise ValueError("\u7a3f\u4ef6\u4e0d\u5b58\u5728\u3002")
        return self.insert_snapshot(connection, post_id, revision_type, snapshot_from_row(row))

    def list(self, post_id: int) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, post_id, revision_type, snapshot_json, created_at
                FROM post_revisions
                WHERE post_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (post_id,),
            ).fetchall()
        items = []
        for row in rows:
            try:
                snapshot = json.loads(row["snapshot_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                snapshot = {}
            items.append({
                "id": row["id"],
                "post_id": row["post_id"],
                "revision_type": row["revision_type"],
                "created_at": row["created_at"],
                "title": snapshot.get("title", ""),
                "status": snapshot.get("status", "draft"),
            })
        return items

    def get(self, post_id: int, revision_id: int) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT id, post_id, revision_type, snapshot_json, created_at
                FROM post_revisions
                WHERE id = ? AND post_id = ?
                """,
                (revision_id, post_id),
            ).fetchone()
        if row is None:
            return None
        try:
            snapshot = json.loads(row["snapshot_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            snapshot = {}
        return {
            "id": row["id"],
            "post_id": row["post_id"],
            "revision_type": row["revision_type"],
            "created_at": row["created_at"],
            "snapshot": snapshot,
        }
