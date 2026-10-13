"""数据库连接与 schema 管理：建表、迁移、站点资料种子。"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .. import uploads
from ..content import SITE_CONFIG
from ..env_loader import project_root
from ..markdown_tools import build_excerpt, render_markdown

ROOT_DIR = project_root()


class Database:
    def __init__(self, db_path: str | os.PathLike[str] | None = None):
        raw_db_path = Path(db_path or os.getenv("BLOG_DATABASE_PATH") or uploads.DEFAULT_DB_PATH)
        self.db_path = raw_db_path if raw_db_path.is_absolute() else ROOT_DIR / raw_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            self._create_schema(connection)
            self._migrate_schema(connection)
            self._seed_site_profile(connection)
            connection.commit()

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS site_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                headline TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                email TEXT DEFAULT '',
                social_links TEXT NOT NULL DEFAULT '[]',
                about_intro TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                excerpt TEXT DEFAULT '',
                published_at TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                read_time TEXT DEFAULT '',
                category TEXT DEFAULT '',
                tags TEXT NOT NULL DEFAULT '[]',
                hero_quote TEXT DEFAULT '',
                cover_image TEXT NOT NULL DEFAULT '',
                click_count INTEGER NOT NULL DEFAULT 0,
                sections TEXT NOT NULL DEFAULT '[]',
                markdown_content TEXT DEFAULT '',
                html_content TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                deleted_at TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS post_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                revision_type TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS media_metadata (
                path TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            -- Login throttling lives in SQLite, not process memory: gunicorn runs
            -- multiple workers (each would keep its own bucket, multiplying the
            -- effective limit) and recycles them via --max-requests, which would
            -- otherwise hand an attacker a free bucket reset.
            CREATE TABLE IF NOT EXISTS login_failures (
                client_key TEXT NOT NULL,
                failed_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_posts_status_pub_order
            ON posts (status, published_at DESC, updated_at DESC, id DESC);

            CREATE INDEX IF NOT EXISTS idx_post_revisions_post_created
            ON post_revisions (post_id, created_at DESC, id DESC);

            CREATE INDEX IF NOT EXISTS idx_login_failures_key_time
            ON login_failures (client_key, failed_at DESC);
            """
        )

    def _migrate_schema(self, connection: sqlite3.Connection) -> None:
        post_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(posts)").fetchall()
        }
        if "click_count" not in post_columns:
            connection.execute("ALTER TABLE posts ADD COLUMN click_count INTEGER NOT NULL DEFAULT 0")
        if "cover_image" not in post_columns:
            connection.execute("ALTER TABLE posts ADD COLUMN cover_image TEXT NOT NULL DEFAULT ''")
        if "deleted_at" not in post_columns:
            connection.execute("ALTER TABLE posts ADD COLUMN deleted_at TEXT DEFAULT NULL")
        # Retired schema: working copies were removed; drop the table and the
        # revision rows that only existed to support them.
        connection.execute("DROP TABLE IF EXISTS post_working_copies")
        connection.execute(
            "DELETE FROM post_revisions WHERE revision_type IN ('discarded_changes', 'restored_to_working_copy')"
        )
        if "featured" in post_columns:
            connection.execute("ALTER TABLE posts DROP COLUMN featured")
        for retired in ("tone", "locale", "translation_of"):
            if retired in post_columns:
                connection.execute(f"ALTER TABLE posts DROP COLUMN {retired}")
        profile_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(site_profile)").fetchall()
        }
        for retired in ("role", "location", "hero_note", "update_calendar", "avatar_path"):
            if retired in profile_columns:
                connection.execute(f"ALTER TABLE site_profile DROP COLUMN {retired}")
        # Legacy auto excerpts kept raw Markdown image syntax; regenerate them.
        legacy_rows = connection.execute(
            "SELECT id, markdown_content FROM posts WHERE excerpt LIKE '%![%'"
        ).fetchall()
        for row in legacy_rows:
            connection.execute(
                "UPDATE posts SET excerpt = ? WHERE id = ?",
                (build_excerpt(row["markdown_content"] or ""), row["id"]),
            )
        self._rerender_markdown_labelled_fences(connection)
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS post_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                revision_type TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS media_metadata (
                path TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS login_failures (
                client_key TEXT NOT NULL,
                failed_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_posts_status_pub_order
            ON posts (status, published_at DESC, updated_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_post_revisions_post_created
            ON post_revisions (post_id, created_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_login_failures_key_time
            ON login_failures (client_key, failed_at DESC);
            """
        )

    def _rerender_markdown_labelled_fences(self, connection: sqlite3.Connection) -> None:
        """重算历史正文里 ```` ```markdown ```` 围栏块的 HTML。

        `html_content` 是写入时渲染的快照，历史数据里那些围栏块被当成了代码，
        表格/标题全部原样输出。这里按 Markdown 源重新渲染一次；渲染结果与库中
        内容相同时不写回，因此重复启动不会产生额外写入。
        """
        legacy = connection.execute(
            "SELECT id, markdown_content, html_content FROM posts WHERE markdown_content LIKE '%```markdown%'"
        ).fetchall()
        for row in legacy:
            rendered = render_markdown(row["markdown_content"] or "")
            if rendered != (row["html_content"] or ""):
                connection.execute(
                    "UPDATE posts SET html_content = ? WHERE id = ?", (rendered, row["id"])
                )

    def _seed_site_profile(self, connection: sqlite3.Connection) -> None:
        count = connection.execute("SELECT COUNT(*) FROM site_profile").fetchone()[0]
        if count:
            return

        now = datetime.now().isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO site_profile (
                id, name, headline, summary, email,
                social_links, about_intro,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                SITE_CONFIG.get("name", ""),
                SITE_CONFIG.get("headline", ""),
                SITE_CONFIG.get("summary", ""),
                SITE_CONFIG.get("email", ""),
                json.dumps(SITE_CONFIG.get("social_links", []), ensure_ascii=False),
                json.dumps(SITE_CONFIG.get("about_intro", []), ensure_ascii=False),
                now,
                now,
            ),
        )
