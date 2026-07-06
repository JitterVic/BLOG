from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

import markdown as markdown_lib
from werkzeug.utils import secure_filename

from content import POSTS, SITE_CONFIG


ROOT_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = ROOT_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR
DEFAULT_DB_PATH = STORAGE_DIR / "blog.db"
ALLOWED_MARKDOWN_EXTENSIONS = {".md", ".markdown"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".jfif", ".avif", ".heic", ".heif"}

JSON_FIELDS = {
    "social_links",
    "about_intro",
    "update_calendar",
    "tags",
    "sections",
}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub("[^0-9A-Za-z_\u4e00-\u9fff-]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or f"post-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def estimate_read_time(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return "1 min"

    english_words = len(re.findall(r"[A-Za-z0-9_]+", cleaned))
    chinese_chars = len(re.findall("[\u4e00-\u9fff]", cleaned))
    units = english_words + chinese_chars
    minutes = max(1, math.ceil(units / 280))
    return f"{minutes} min"


def sections_to_markdown(sections: list[dict[str, Any]]) -> str:
    chunks = []
    for section in sections:
        heading = section.get("heading")
        if heading:
            chunks.append(f"## {heading}")
        chunks.extend(section.get("paragraphs") or [])
    return "\n\n".join(chunks).strip()


def render_markdown(markdown_text: str) -> str:
    return markdown_lib.markdown(
        markdown_text or "",
        extensions=["extra", "fenced_code", "tables", "nl2br"],
    )


def decode_markdown_file(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def get_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def validate_extension(filename: str, allowed_extensions: set[str], label: str) -> None:
    extension = get_extension(filename)
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(f"{label}格式不支持，请使用：{allowed}")


class BlogStore:
    def __init__(self, db_path: str | os.PathLike[str] | None = None):
        raw_db_path = Path(db_path or os.getenv("BLOG_DATABASE_PATH") or DEFAULT_DB_PATH)
        self.db_path = raw_db_path if raw_db_path.is_absolute() else ROOT_DIR / raw_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        (UPLOADS_DIR / "avatars").mkdir(parents=True, exist_ok=True)
        (UPLOADS_DIR / "media").mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init(self) -> None:
        with self.connect() as connection:
            self._create_schema(connection)
            self._migrate_schema(connection)
            self._seed_site_profile(connection)
            self._seed_posts(connection)
            connection.commit()

    def _create_schema(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS site_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                role TEXT DEFAULT '',
                headline TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                location TEXT DEFAULT '',
                email TEXT DEFAULT '',
                hero_note TEXT DEFAULT '',
                social_links TEXT NOT NULL DEFAULT '[]',
                about_intro TEXT NOT NULL DEFAULT '[]',
                update_calendar TEXT NOT NULL DEFAULT '[]',
                avatar_path TEXT DEFAULT '',
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
                featured INTEGER NOT NULL DEFAULT 0,
                tone TEXT DEFAULT 'amber',
                tags TEXT NOT NULL DEFAULT '[]',
                hero_quote TEXT DEFAULT '',
                click_count INTEGER NOT NULL DEFAULT 0,
                sections TEXT NOT NULL DEFAULT '[]',
                markdown_content TEXT DEFAULT '',
                html_content TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft'
            );
            """
        )

    def _migrate_schema(self, connection: sqlite3.Connection) -> None:
        post_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(posts)").fetchall()
        }
        if "click_count" not in post_columns:
            connection.execute("ALTER TABLE posts ADD COLUMN click_count INTEGER NOT NULL DEFAULT 0")


    def _seed_site_profile(self, connection: sqlite3.Connection) -> None:
        count = connection.execute("SELECT COUNT(*) FROM site_profile").fetchone()[0]
        if count:
            return

        now = datetime.now().isoformat(timespec="seconds")
        connection.execute(
            """
            INSERT INTO site_profile (
                id, name, role, headline, summary, location, email, hero_note,
                social_links, about_intro, update_calendar, avatar_path,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                SITE_CONFIG.get("name", ""),
                SITE_CONFIG.get("role", ""),
                SITE_CONFIG.get("headline", ""),
                SITE_CONFIG.get("summary", ""),
                SITE_CONFIG.get("location", ""),
                SITE_CONFIG.get("email", ""),
                SITE_CONFIG.get("hero_note", ""),
                json.dumps(SITE_CONFIG.get("social_links", []), ensure_ascii=False),
                json.dumps(SITE_CONFIG.get("about_intro", []), ensure_ascii=False),
                json.dumps(SITE_CONFIG.get("update_calendar", []), ensure_ascii=False),
                "",
                now,
                now,
            ),
        )

    def _seed_posts(self, connection: sqlite3.Connection) -> None:
        count = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        if count:
            return

        now = datetime.now().isoformat(timespec="seconds")
        for post in POSTS:
            markdown_content = sections_to_markdown(post.get("sections", []))
            html_content = render_markdown(markdown_content)
            connection.execute(
                """
                INSERT INTO posts (
                    slug, title, excerpt, published_at, created_at, updated_at,
                    read_time, category, featured, tone, tags, hero_quote,
                    sections, markdown_content, html_content, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    post.get("slug"),
                    post.get("title", ""),
                    post.get("excerpt", ""),
                    post.get("published_at", ""),
                    now,
                    now,
                    post.get("read_time") or estimate_read_time(markdown_content),
                    post.get("category", ""),
                    1 if post.get("featured") else 0,
                    post.get("tone", "amber"),
                    json.dumps(post.get("tags", []), ensure_ascii=False),
                    post.get("hero_quote", ""),
                    json.dumps(post.get("sections", []), ensure_ascii=False),
                    markdown_content,
                    html_content,
                    "published",
                ),
            )

    def _row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        data = dict(row)
        for field in JSON_FIELDS:
            if field in data:
                data[field] = json.loads(data[field] or "[]")
        return data

    def _avatar_url(self, avatar_path: str) -> str:
        if not avatar_path:
            return ""
        normalized = avatar_path.replace("\\", "/")
        return "/uploads/" + normalized

    def ensure_unique_slug(self, desired_slug: str, *, post_id: int | None = None) -> str:
        base_slug = slugify(desired_slug)
        candidate = base_slug
        counter = 2

        with self.connect() as connection:
            while True:
                row = connection.execute(
                    "SELECT id FROM posts WHERE slug = ?",
                    (candidate,),
                ).fetchone()
                if row is None or (post_id and row["id"] == post_id):
                    return candidate
                candidate = f"{base_slug}-{counter}"
                counter += 1

    def get_site_profile(self) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM site_profile WHERE id = 1").fetchone()
        profile = self._row_to_dict(row) or {}
        profile["avatar_url"] = self._avatar_url(profile.get("avatar_path", ""))
        return profile

    def get_site_payload(self) -> dict[str, Any]:
        profile = self.get_site_profile()
        posts = self.list_posts(published_only=True)
        tags = sorted({tag for post in posts for tag in post.get("tags", [])})
        featured_post = next((post for post in posts if post.get("featured")), None)

        payload = {**SITE_CONFIG, **profile}
        payload["tags"] = tags
        payload["featured_post"] = featured_post
        return payload

    def list_posts(
        self,
        *,
        tag: str | None = None,
        featured: bool | None = None,
        published_only: bool = True,
        sort: str = "latest",
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM posts"
        conditions = []
        params: list[Any] = []

        if published_only:
            conditions.append("status = 'published'")
        if featured is not None:
            conditions.append("featured = ?")
            params.append(1 if featured else 0)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        if sort == "hot":
            query += " ORDER BY click_count DESC, published_at DESC, updated_at DESC"
        else:
            query += " ORDER BY published_at DESC, updated_at DESC"

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()

        posts = [self._row_to_dict(row) for row in rows]
        if tag:
            lowered = tag.lower()
            posts = [
                post
                for post in posts
                if lowered in {item.lower() for item in post.get("tags", [])}
            ]
        return posts

    def get_post_by_slug(self, slug: str, *, include_drafts: bool = False) -> dict[str, Any] | None:
        query = "SELECT * FROM posts WHERE slug = ?"
        params: list[Any] = [slug]
        if not include_drafts:
            query += " AND status = 'published'"

        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return self._row_to_dict(row)

    def increment_post_click(self, slug: str) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE posts
                SET click_count = COALESCE(click_count, 0) + 1, updated_at = updated_at
                WHERE slug = ? AND status = 'published'
                """,
                (slug,),
            )
            connection.commit()

    def get_post_by_id(self, post_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return self._row_to_dict(row)

    def list_admin_posts(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM posts ORDER BY updated_at DESC, created_at DESC"
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_site_profile(self, form_data: dict[str, Any], avatar_file=None) -> None:
        current = self.get_site_profile()
        avatar_path = current.get("avatar_path", "")
        if avatar_file and avatar_file.filename:
            avatar_path = self.save_file(
                avatar_file,
                "avatars",
                allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
                label="头像图片",
            )

        name = form_data.get("name", "").strip() or current.get("name", "")
        if not name:
            raise ValueError("站点名称不能为空。")

        email = form_data.get("email", "").strip()
        role = form_data.get("role", "").strip()
        headline = form_data.get("headline", "").strip()
        summary = form_data.get("summary", "").strip()
        github_label = form_data.get("github_label", "").strip()
        github_url = form_data.get("github_url", "").strip()

        social_links = []
        if email:
            social_links.append(
                {
                    "label": "邮箱",
                    "value": email,
                    "url": f"mailto:{email}",
                    "icon": "mail",
                }
            )
        if github_label or github_url:
            social_links.append(
                {
                    "label": "GitHub 仓库",
                    "value": github_label or github_url,
                    "url": github_url,
                    "icon": "github",
                }
            )

        about_intro = [line.strip() for line in form_data.get("about_intro", "").splitlines() if line.strip()]
        update_calendar = []
        for line in form_data.get("update_calendar", "").splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if "|" in cleaned:
                left, right = cleaned.split("|", 1)
                update_calendar.append({"date": left.strip(), "title": right.strip()})
            else:
                update_calendar.append({"date": date.today().isoformat(), "title": cleaned})

        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE site_profile
                SET name = ?, role = ?, headline = ?, summary = ?, location = ?,
                    email = ?, hero_note = ?, social_links = ?, about_intro = ?,
                    update_calendar = ?, avatar_path = ?, updated_at = ?
                WHERE id = 1
                """,
                (
                    name,
                    role,
                    headline,
                    summary,
                    form_data.get("location", "").strip(),
                    email,
                    form_data.get("hero_note", "").strip(),
                    json.dumps(social_links, ensure_ascii=False),
                    json.dumps(about_intro, ensure_ascii=False),
                    json.dumps(update_calendar, ensure_ascii=False),
                    avatar_path,
                    now,
                ),
            )
            connection.commit()

    def save_post(self, form_data: dict[str, Any], *, post_id: int | None = None, action: str = "draft") -> int:
        title = form_data.get("title", "").strip()
        if not title:
            raise ValueError("文章标题不能为空。")

        markdown_content = form_data.get("markdown_content", "").strip()
        html_content = render_markdown(markdown_content)
        excerpt = form_data.get("excerpt", "").strip() or self.build_excerpt(markdown_content)
        slug = self.ensure_unique_slug(form_data.get("slug", "") or title, post_id=post_id)
        published = action == "published"
        status = "published" if published else "draft"
        published_at = form_data.get("published_at", "").strip()
        if published and not published_at:
            published_at = date.today().isoformat()

        tags = [item.strip() for item in form_data.get("tags", "").split(",") if item.strip()]
        featured = 1 if form_data.get("featured") == "on" else 0
        read_time = form_data.get("read_time", "").strip() or estimate_read_time(markdown_content)
        category = form_data.get("category", "").strip()
        tone = form_data.get("tone", "amber").strip() or "amber"
        hero_quote = form_data.get("hero_quote", "").strip()
        sections = json.dumps([], ensure_ascii=False)
        tags_json = json.dumps(tags, ensure_ascii=False)
        now = datetime.now().isoformat(timespec="seconds")

        with self.connect() as connection:
            if post_id:
                connection.execute(
                    """
                    UPDATE posts
                    SET slug = ?, title = ?, excerpt = ?, published_at = ?, updated_at = ?,
                        read_time = ?, category = ?, featured = ?, tone = ?, tags = ?,
                        hero_quote = ?, sections = ?, markdown_content = ?, html_content = ?,
                        status = ?
                    WHERE id = ?
                    """,
                    (
                        slug,
                        title,
                        excerpt,
                        published_at,
                        now,
                        read_time,
                        category,
                        featured,
                        tone,
                        tags_json,
                        hero_quote,
                        sections,
                        markdown_content,
                        html_content,
                        status,
                        post_id,
                    ),
                )
                saved_id = post_id
            else:
                connection.execute(
                    """
                    INSERT INTO posts (
                        slug, title, excerpt, published_at, created_at, updated_at,
                        read_time, category, featured, tone, tags, hero_quote,
                        sections, markdown_content, html_content, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        slug,
                        title,
                        excerpt,
                        published_at,
                        now,
                        now,
                        read_time,
                        category,
                        featured,
                        tone,
                        tags_json,
                        hero_quote,
                        sections,
                        markdown_content,
                        html_content,
                        status,
                    ),
                )
                saved_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.commit()
        return saved_id

    def delete_post(self, post_id: int) -> None:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            connection.commit()
        if cursor.rowcount == 0:
            raise ValueError("文章不存在或已经被删除。")

    def build_excerpt(self, markdown_content: str) -> str:
        text = re.sub(r"[#>*`\-]", " ", markdown_content)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:120] + ("..." if len(text) > 120 else "")

    def save_file(
        self,
        file_storage,
        folder: str,
        *,
        allowed_extensions: set[str] | None = None,
        label: str = "??",
    ) -> str:
        original_filename = (file_storage.filename or "file").strip()
        if allowed_extensions:
            validate_extension(original_filename, allowed_extensions, label)

        source_path = Path(original_filename)
        suffix = source_path.suffix.lower()
        safe_stem = secure_filename(source_path.stem) or "file"
        unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{safe_stem}{suffix}"
        relative_path = Path(folder) / unique_name
        destination = UPLOADS_DIR / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        file_storage.save(destination)
        return relative_path.as_posix()

    def import_markdown(self, file_storage) -> dict[str, Any]:
        validate_extension(file_storage.filename or "", ALLOWED_MARKDOWN_EXTENSIONS, "Markdown 文件")
        content = decode_markdown_file(file_storage.read())
        guessed_title = ""
        for line in content.splitlines():
            if line.startswith("# "):
                guessed_title = line[2:].strip()
                break
        return {
            "title": guessed_title,
            "slug": slugify(guessed_title) if guessed_title else "",
            "markdown_content": content,
            "html_content": render_markdown(content),
            "excerpt": self.build_excerpt(content),
            "read_time": estimate_read_time(content),
        }

    def upload_media(self, file_storage) -> dict[str, str]:
        relative_path = self.save_file(
            file_storage,
            "media",
            allowed_extensions=ALLOWED_IMAGE_EXTENSIONS,
            label="图片",
        )
        return {
            "path": relative_path,
            "url": "/uploads/" + relative_path,
        }

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            post_count = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            draft_count = connection.execute("SELECT COUNT(*) FROM posts WHERE status = 'draft'").fetchone()[0]
            published_count = connection.execute("SELECT COUNT(*) FROM posts WHERE status = 'published'").fetchone()[0]
        return {
            "db_path": str(self.db_path),
            "post_count": post_count,
            "published_count": published_count,
            "draft_count": draft_count,
            "upload_dir": str(UPLOADS_DIR),
        }




