"""数据库连接与 schema 管理：建表、迁移、站点资料种子。"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .. import uploads
from ..env_loader import project_root
from ..markdown_tools import build_excerpt, render_markdown

ROOT_DIR = project_root()


# 站点资料的种子值：仅在 site_profile 为空时写入一次（之后一律走后台编辑）。
# 之前单独放在 content.py，只有一个常量、只有一个使用方，属于无谓的间接层。
SITE_SEED = {
    "name": "",
    "headline": "",
    "summary": "",
    "email": "",
    "social_links": [],
    "about_intro": [],
}



class Database:
    def __init__(self, db_path: str | os.PathLike[str] | None = None):
        raw_db_path = Path(db_path or os.getenv("BLOG_DATABASE_PATH") or uploads.DEFAULT_DB_PATH)
        self.db_path = raw_db_path if raw_db_path.is_absolute() else ROOT_DIR / raw_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._wal_ready = False

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        self._ensure_journal_mode(connection)
        return connection

    def _ensure_journal_mode(self, connection: sqlite3.Connection) -> None:
        """确保日志模式为 WAL —— 但每个 Database 实例只做一次。

        journal_mode 是写进数据库文件的持久属性，不需要（也不应该）每条连接重设。
        实测差别很大：带这条 PRAGMA 的连接 0.93ms，不带 0.13ms；连「只读回 journal_mode」
        都要 0.91ms（它同样要碰 WAL 与文件锁）。而一次请求会开 2~4 条连接，
        重复设置等于白扔 1.5~3ms。init() 会重置这个标记，所以「恢复数据库后重新 init」
        仍然会重新确认日志模式。
        """
        if self._wal_ready:
            return
        connection.execute("PRAGMA journal_mode = WAL")
        self._wal_ready = True

    def init(self) -> None:
        # 建表/迁移是一次明确的引导动作，此时重新确认日志模式：数据库文件可能刚被
        # 备份还原替换过，而那条路径不会重启进程。
        self._wal_ready = False
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
                keywords TEXT NOT NULL DEFAULT '[]',
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

            -- 前台首页「热点文章」按 click_count 排序。没有这条索引时，计划里会出现
            -- USE TEMP B-TREE FOR ORDER BY：每次都要把全部已发布稿件读出来排一遍
            -- （400 篇实测 2.40ms）。加上后计划变成 COVERING INDEX，降到 0.34ms。
            CREATE INDEX IF NOT EXISTS idx_posts_hot
            ON posts (status, click_count DESC, published_at DESC, updated_at DESC, id DESC);

            -- 标签词表（/api/site 与后台写作页）只用到 status 与 tags 两列。缺这条覆盖索引时
            -- 聚合得回表把每篇整行（含正文）读出来，400 篇实测 3.47ms；加上后 0.56ms。
            CREATE INDEX IF NOT EXISTS idx_posts_status_tags
            ON posts (status, tags);

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
        if "keywords" not in post_columns:
            # 关键词只参与检索、不对外展示，因此同样以 JSON 数组存放。
            connection.execute("ALTER TABLE posts ADD COLUMN keywords TEXT NOT NULL DEFAULT '[]'")
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
        self._refresh_stale_html_content(connection)
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

    def _refresh_stale_html_content(self, connection: sqlite3.Connection) -> None:
        """用最新的渲染器重算围栏代码块的 HTML 快照。

        `html_content` 是写入时渲染的快照，历史数据里「围栏里其实是 Markdown」
        的内容被当成了代码，表格/列表全部原样输出。渲染器升级后这些快照就过期了，
        这里按 Markdown 源重新渲染一次；只有结果不同才写回，因此重复启动不产生
        额外写入（幂等）。
        """
        stale = connection.execute(
            "SELECT id, markdown_content, html_content FROM posts WHERE markdown_content LIKE '%```%'"
        ).fetchall()
        for row in stale:
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
                SITE_SEED.get("name", ""),
                SITE_SEED.get("headline", ""),
                SITE_SEED.get("summary", ""),
                SITE_SEED.get("email", ""),
                json.dumps(SITE_SEED.get("social_links", []), ensure_ascii=False),
                json.dumps(SITE_SEED.get("about_intro", []), ensure_ascii=False),
                now,
                now,
            ),
        )
