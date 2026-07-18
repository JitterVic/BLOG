from __future__ import annotations

import html
import io
import json
import math
import os
import re
import sqlite3
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

import markdown as markdown_lib
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

try:
    from .content import POSTS, SITE_CONFIG
    from .env_loader import env_int
except ImportError:
    from content import POSTS, SITE_CONFIG
    from env_loader import env_int


ROOT_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = ROOT_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR
DEFAULT_DB_PATH = STORAGE_DIR / "blog.db"
ALLOWED_MARKDOWN_EXTENSIONS = {".md", ".markdown"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".jfif", ".avif", ".heic", ".heif"}
UPLOAD_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".jfif"}
IMAGE_FORMAT_EXTENSIONS = {
    "PNG": {".png"}, "JPEG": {".jpg", ".jpeg", ".jfif"},
    "GIF": {".gif"}, "WEBP": {".webp"}, "BMP": {".bmp"},
}
IMAGE_MIME_TYPES = {
    "PNG": {"image/png"}, "JPEG": {"image/jpeg", "image/jpg", "image/pjpeg"},
    "GIF": {"image/gif"}, "WEBP": {"image/webp"},
    "BMP": {"image/bmp", "image/x-ms-bmp"},
}
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 20_000_000
MAX_FIELD_LENGTHS = {
    "name": 120, "role": 160, "location": 160, "headline": 240,
    "summary": 1000, "email": 320, "hero_note": 500,
    "github_label": 240, "github_url": 2048, "about_intro": 12_000,
    "update_calendar": 12_000, "title": 240, "slug": 240,
    "excerpt": 1200, "published_at": 32, "read_time": 32,
    "category": 120, "tags": 1200, "hero_quote": 1000,
    "cover_image": 2048, "markdown_content": 500_000,
}
PUBLIC_UPLOAD_FOLDERS = {"avatars", "media"}

JSON_FIELDS = {
    "social_links",
    "about_intro",
    "update_calendar",
    "tags",
    "sections",
}

# Compact columns for list/related responses. Keep detail queries on SELECT *
# so markdown/html only load when a single post is opened.
LIST_POST_COLUMNS = (
    "id, slug, title, excerpt, published_at, created_at, updated_at, "
    "read_time, category, featured, tone, tags, hero_quote, cover_image, "
    "status, click_count"
)
ADMIN_LIST_LIMIT = 200


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub("[^0-9A-Za-z_\u4e00-\u9fff-]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-") or f"post-{datetime.now().strftime('%Y%m%d%H%M%S')}"


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


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


FRONT_MATTER_KEYS = {
    "title",
    "slug",
    "tags",
    "category",
    "date",
    "cover",
    "excerpt",
    "hero_quote",
}


def _strip_front_matter_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value


def _parse_front_matter_tags(value: str) -> list[str]:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [
        tag
        for item in value.split(",")
        if (tag := _strip_front_matter_quotes(item))
    ]


def parse_markdown_front_matter(content: str) -> tuple[dict[str, Any], str]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, content

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing_index is None:
        return {}, content

    metadata: dict[str, Any] = {}
    for line in lines[1:closing_index]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip().lower()
        if key not in FRONT_MATTER_KEYS:
            continue
        if key == "tags":
            metadata[key] = _parse_front_matter_tags(raw_value)
        else:
            metadata[key] = _strip_front_matter_quotes(raw_value)

    body = "\n".join(lines[closing_index + 1:]).lstrip("\n")
    return metadata, body


ALLOWED_HTML_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
ALLOWED_HTML_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
    "td": {"align", "colspan", "rowspan"},
    "th": {"align", "colspan", "rowspan"},
    "ol": {"start"},
}
HTML_VOID_TAGS = {"br", "hr", "img"}
HTML_DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "svg", "math", "template"}
SAFE_CLASS_RE = re.compile(r"^[A-Za-z0-9_\- ]{1,80}$")
SAFE_INT_RE = re.compile(r"^[1-9][0-9]{0,2}$")
URL_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")


def _normalize_url_for_scheme(value: str) -> str:
    return re.sub(r"[\x00-\x20]+", "", value or "").lower()


def _has_colon_before_path_marker(value: str) -> bool:
    marker_positions = [pos for marker in ("/", "?", "#") if (pos := value.find(marker)) >= 0]
    first_marker = min(marker_positions) if marker_positions else len(value)
    colon = value.find(":")
    return 0 <= colon < first_marker


def _is_safe_link_url(value: str) -> bool:
    cleaned = (value or "").strip()
    normalized = _normalize_url_for_scheme(cleaned)
    if not cleaned or normalized.startswith("//"):
        return False
    scheme_match = URL_SCHEME_RE.match(normalized)
    if scheme_match:
        return scheme_match.group(1) in {"http", "https", "mailto"}
    return not _has_colon_before_path_marker(normalized)


def is_allowed_public_upload_path(path: str) -> bool:
    decoded_path = unquote(path or "").replace("\\", "/").strip()
    if not decoded_path or decoded_path.startswith("/"):
        return False

    parts = PurePosixPath(decoded_path).parts
    if len(parts) < 2 or parts[0] not in PUBLIC_UPLOAD_FOLDERS:
        return False
    if any(part in {"", ".", ".."} for part in parts):
        return False

    return get_extension(parts[-1]) in ALLOWED_IMAGE_EXTENSIONS


def _is_safe_image_url(value: str) -> bool:
    cleaned = (value or "").strip()
    normalized = _normalize_url_for_scheme(cleaned)
    if not cleaned or normalized.startswith("//"):
        return False
    scheme_match = URL_SCHEME_RE.match(normalized)
    if scheme_match:
        return scheme_match.group(1) in {"http", "https"}

    parsed = urlsplit(cleaned)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/uploads/"):
        return False
    return is_allowed_public_upload_path(parsed.path.removeprefix("/uploads/"))


def _clean_attr(tag: str, name: str, value: str | None) -> tuple[str, str] | None:
    attr = name.lower().strip()
    if attr.startswith("on") or attr not in ALLOWED_HTML_ATTRS.get(tag, set()):
        return None

    cleaned = (value or "").strip()
    if attr == "href" and not _is_safe_link_url(cleaned):
        return None
    if attr == "src" and not _is_safe_image_url(cleaned):
        return None
    if attr == "class" and not SAFE_CLASS_RE.fullmatch(cleaned):
        return None
    if attr in {"colspan", "rowspan", "start"} and not SAFE_INT_RE.fullmatch(cleaned):
        return None
    if attr == "align" and cleaned not in {"left", "center", "right"}:
        return None
    return attr, cleaned


class SafeHTMLCleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._append_starttag(tag, attrs, is_self_closing=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._append_starttag(tag, attrs, is_self_closing=True)

    def _append_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        *,
        is_self_closing: bool,
    ) -> None:
        tag = tag.lower()
        if tag in HTML_DROP_CONTENT_TAGS:
            if not is_self_closing:
                self.drop_depth += 1
            return
        if self.drop_depth or tag not in ALLOWED_HTML_TAGS:
            return

        cleaned_attrs = []
        for name, value in attrs:
            cleaned = _clean_attr(tag, name, value)
            if cleaned:
                attr, attr_value = cleaned
                cleaned_attrs.append(f'{attr}="{html.escape(attr_value, quote=True)}"')

        attr_text = " " + " ".join(cleaned_attrs) if cleaned_attrs else ""
        self.parts.append(f"<{tag}{attr_text}>")
        if tag not in HTML_VOID_TAGS and not is_self_closing:
            self.open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in HTML_DROP_CONTENT_TAGS:
            if self.drop_depth:
                self.drop_depth -= 1
            return
        if self.drop_depth or tag not in ALLOWED_HTML_TAGS or tag in HTML_VOID_TAGS:
            return
        if tag in self.open_tags:
            while self.open_tags:
                open_tag = self.open_tags.pop()
                self.parts.append(f"</{open_tag}>")
                if open_tag == tag:
                    break

    def handle_data(self, data: str) -> None:
        if not self.drop_depth:
            self.parts.append(html.escape(data))

    def get_html(self) -> str:
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


def sanitize_html(html_text: str) -> str:
    cleaner = SafeHTMLCleaner()
    cleaner.feed(html_text or "")
    cleaner.close()
    return cleaner.get_html()


def render_markdown(markdown_text: str) -> str:
    rendered = markdown_lib.markdown(
        markdown_text or "",
        extensions=["extra", "fenced_code", "tables", "nl2br"],
    )
    return sanitize_html(rendered)


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


def validate_text_length(field: str, value: str, *, max_length: int | None = None) -> str:
    normalized = str(value or "").strip()
    limit = max_length or MAX_FIELD_LENGTHS.get(field)
    if limit and len(normalized) > limit:
        raise ValueError(f"{field}内容过长，请控制在 {limit} 个字符以内。")
    return normalized


def validate_image_upload(file_storage, *, max_bytes: int, max_pixels: int) -> bytes:
    filename = (file_storage.filename or "").strip()
    extension = get_extension(filename)
    validate_extension(filename, UPLOAD_IMAGE_EXTENSIONS, "图片")
    mimetype = (file_storage.mimetype or "").lower().split(";", 1)[0].strip()
    if mimetype and not mimetype.startswith("image/"):
        raise ValueError("图片 MIME 类型无效，请选择真实的图片文件。")
    stream = file_storage.stream
    stream.seek(0)
    raw_bytes = stream.read(max_bytes + 1)
    stream.seek(0)
    if len(raw_bytes) > max_bytes:
        raise ValueError(f"图片过大，请控制在 {max_bytes // (1024 * 1024)} MB 以内。")
    if not raw_bytes:
        raise ValueError("图片文件为空。")
    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("图片内容无法识别，请上传有效的图片文件。") from exc
    if image_format not in IMAGE_FORMAT_EXTENSIONS or extension not in IMAGE_FORMAT_EXTENSIONS[image_format]:
        raise ValueError("图片扩展名、MIME 类型与真实图片格式不一致。")
    if mimetype and mimetype not in IMAGE_MIME_TYPES.get(image_format, set()):
        raise ValueError("图片 MIME 类型与真实图片格式不一致。")
    if width <= 0 or height <= 0 or width * height > max_pixels:
        raise ValueError(f"图片尺寸过大，请控制在 {max_pixels:,} 像素以内。")
    return raw_bytes


class PostVersionConflict(ValueError):
    """Raised when an autosave would overwrite a newer server version."""


class BlogStore:
    def __init__(self, db_path: str | os.PathLike[str] | None = None):
        raw_db_path = Path(db_path or os.getenv("BLOG_DATABASE_PATH") or DEFAULT_DB_PATH)
        self.db_path = raw_db_path if raw_db_path.is_absolute() else ROOT_DIR / raw_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        (UPLOADS_DIR / "avatars").mkdir(parents=True, exist_ok=True)
        (UPLOADS_DIR / "media").mkdir(parents=True, exist_ok=True)
        self.max_file_bytes = env_int("BLOG_MAX_UPLOAD_BYTES", 10 * 1024 * 1024, minimum=1)
        self.max_image_bytes = env_int("BLOG_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES, minimum=1)
        self.max_image_pixels = env_int("BLOG_MAX_IMAGE_PIXELS", DEFAULT_MAX_IMAGE_PIXELS, minimum=1)

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
                cover_image TEXT NOT NULL DEFAULT '',
                click_count INTEGER NOT NULL DEFAULT 0,
                sections TEXT NOT NULL DEFAULT '[]',
                markdown_content TEXT DEFAULT '',
                html_content TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft'
            );

            CREATE INDEX IF NOT EXISTS idx_posts_status_pub_order
            ON posts (status, published_at DESC, updated_at DESC, id DESC);
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
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_posts_status_pub_order
            ON posts (status, published_at DESC, updated_at DESC, id DESC)
            """
        )


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
        if "html_content" in data:
            data["html_content"] = data.get("html_content") or (
                render_markdown(data.get("markdown_content", ""))
                if data.get("markdown_content")
                else ""
            )
        # List queries intentionally omit body columns; keep keys absent rather
        # than inventing empty markdown/html fields.
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
        tags: set[str] = set()
        with self.connect() as connection:
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

        payload = {key: value for key, value in SITE_CONFIG.items() if key != "featured_slug"}
        payload.update(profile)
        payload["tags"] = sorted(tags)
        return payload

    def _build_post_filters(
        self,
        *,
        tag: str | None = None,
        featured: bool | None = None,
        published_only: bool = True,
        search: str | None = None,
    ) -> tuple[str, list[Any]]:
        conditions = []
        params: list[Any] = []

        if published_only:
            conditions.append("status = 'published'")
        if featured is not None:
            conditions.append("featured = ?")
            params.append(1 if featured else 0)
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
    def _post_order_clause(sort: str = "latest") -> str:
        if sort == "hot":
            return " ORDER BY click_count DESC, published_at DESC, updated_at DESC, id DESC"
        return " ORDER BY published_at DESC, updated_at DESC, id DESC"

    def count_posts(
        self,
        *,
        tag: str | None = None,
        featured: bool | None = None,
        published_only: bool = True,
        search: str | None = None,
    ) -> int:
        where_sql, params = self._build_post_filters(
            tag=tag,
            featured=featured,
            published_only=published_only,
            search=search,
        )
        with self.connect() as connection:
            row = connection.execute(f"SELECT COUNT(*) FROM posts{where_sql}", params).fetchone()
        return int(row[0] if row else 0)

    def list_posts(
        self,
        *,
        tag: str | None = None,
        featured: bool | None = None,
        published_only: bool = True,
        sort: str = "latest",
        search: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        where_sql, params = self._build_post_filters(
            tag=tag,
            featured=featured,
            published_only=published_only,
            search=search,
        )
        query = f"SELECT {LIST_POST_COLUMNS} FROM posts{where_sql}{self._post_order_clause(sort)}"
        if limit is not None:
            query += " LIMIT ?"
            params.append(max(0, int(limit)))
            if offset is not None:
                query += " OFFSET ?"
                params.append(max(0, int(offset)))
        elif offset is not None:
            query += " LIMIT -1 OFFSET ?"
            params.append(max(0, int(offset)))

        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_adjacent_posts(
        self,
        post: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        current = (
            post.get("published_at") or "",
            post.get("updated_at") or "",
            int(post.get("id") or 0),
        )

        with self.connect() as connection:
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

        return self._row_to_dict(previous_row), self._row_to_dict(next_row)

    def get_post_by_slug(self, slug: str, *, include_drafts: bool = False) -> dict[str, Any] | None:
        query = "SELECT * FROM posts WHERE slug = ?"
        params: list[Any] = [slug]
        if not include_drafts:
            query += " AND status = 'published'"

        with self.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return self._row_to_dict(row)

    def increment_post_click(self, slug: str) -> int:
        """Increase public view count once. Returns the updated click_count (or current if missing)."""
        with self.connect() as connection:
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

        with self.connect() as connection:
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

        candidates = [self._row_to_dict(row) for row in rows]

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

    def get_post_by_id(self, post_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        return self._row_to_dict(row)

    def list_admin_posts(self, *, limit: int = ADMIN_LIST_LIMIT) -> list[dict[str, Any]]:
        capped = max(1, min(int(limit or ADMIN_LIST_LIMIT), ADMIN_LIST_LIMIT))
        with self.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT {LIST_POST_COLUMNS}
                FROM posts
                ORDER BY updated_at DESC, created_at DESC
                LIMIT ?
                """,
                (capped,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_site_profile(self, form_data: dict[str, Any], avatar_file=None) -> None:
        current = self.get_site_profile()
        avatar_path = current.get("avatar_path", "")
        if avatar_file and avatar_file.filename:
            avatar_path = self.save_file(avatar_file, "avatars", label="头像图片")

        values = {
            field: validate_text_length(field, form_data.get(field, ""))
            for field in (
                "name", "role", "location", "headline", "summary", "email",
                "hero_note", "github_label", "github_url", "about_intro", "update_calendar",
            )
        }
        name = values["name"] or current.get("name", "")
        if not name:
            raise ValueError("站点名称不能为空。")
        email = values["email"]
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValueError("Email 格式无效。")
        github_label = values["github_label"]
        github_url = values["github_url"]
        if github_url and not re.match(r"^https?://", github_url, re.IGNORECASE):
            raise ValueError("GitHub 链接必须使用 http:// 或 https://。")

        social_links = []
        if email:
            social_links.append({"label": "邮箱", "value": email, "url": f"mailto:{email}", "icon": "mail"})
        if github_label or github_url:
            social_links.append({"label": "GitHub 仓库", "value": github_label or github_url, "url": github_url, "icon": "github"})

        about_intro = [line.strip() for line in values["about_intro"].splitlines() if line.strip()]
        update_calendar = []
        for line in values["update_calendar"].splitlines():
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
                    name, values["role"], values["headline"], values["summary"], values["location"],
                    email, values["hero_note"], json.dumps(social_links, ensure_ascii=False),
                    json.dumps(about_intro, ensure_ascii=False), json.dumps(update_calendar, ensure_ascii=False),
                    avatar_path, now,
                ),
            )
            connection.commit()

    def save_post(
        self,
        form_data: dict[str, Any],
        *,
        post_id: int | None = None,
        action: str = "draft",
        expected_updated_at: str | None = None,
    ) -> int:
        if action not in {"draft", "published"}:
            raise ValueError("文章状态无效。")
        title = validate_text_length("title", form_data.get("title", ""))
        if not title:
            raise ValueError("文章标题不能为空。")
        markdown_content = validate_text_length("markdown_content", form_data.get("markdown_content", ""))
        html_content = render_markdown(markdown_content)
        excerpt = validate_text_length("excerpt", form_data.get("excerpt", "")) or self.build_excerpt(markdown_content)
        raw_slug = validate_text_length("slug", form_data.get("slug", ""))
        slug = self.ensure_unique_slug(raw_slug or title, post_id=post_id)
        published = action == "published"
        status = "published" if published else "draft"
        published_at = validate_text_length("published_at", form_data.get("published_at", ""))
        if published and not published_at:
            published_at = date.today().isoformat()

        tags_text = validate_text_length("tags", form_data.get("tags", ""))
        tags = [validate_text_length("tag", item, max_length=80) for item in tags_text.split(",") if item.strip()]
        if len(tags) > 40:
            raise ValueError("标签数量过多，请控制在 40 个以内。")
        featured = 0
        read_time = validate_text_length("read_time", form_data.get("read_time", "")) or estimate_read_time(markdown_content)
        category = validate_text_length("category", form_data.get("category", ""))
        tone = "amber"
        hero_quote = validate_text_length("hero_quote", form_data.get("hero_quote", ""))
        cover_image = validate_text_length("cover_image", form_data.get("cover_image", ""))
        if cover_image and not _is_safe_image_url(cover_image):
            raise ValueError("封面图片地址无效：请使用上传得到的 /uploads/ 地址或 http(s) 图片链接。")
        sections = json.dumps([], ensure_ascii=False)
        tags_json = json.dumps(tags, ensure_ascii=False)
        now = datetime.now().isoformat(timespec="microseconds")

        with self.connect() as connection:
            if post_id:
                if expected_updated_at is not None:
                    current_row = connection.execute("SELECT updated_at FROM posts WHERE id = ?", (post_id,)).fetchone()
                    if current_row is None:
                        raise ValueError("稿件不存在。")
                    if current_row["updated_at"] != expected_updated_at:
                        raise PostVersionConflict("文章已在其他页面更新，请重新加载后再保存。")
                connection.execute(
                    """
                    UPDATE posts
                    SET slug = ?, title = ?, excerpt = ?, published_at = ?, updated_at = ?,
                        read_time = ?, category = ?, featured = ?, tone = ?, tags = ?,
                        hero_quote = ?, cover_image = ?, sections = ?, markdown_content = ?,
                        html_content = ?, status = ?
                    WHERE id = ?
                    """,
                    (slug, title, excerpt, published_at, now, read_time, category, featured, tone, tags_json,
                     hero_quote, cover_image, sections, markdown_content, html_content, status, post_id),
                )
                saved_id = post_id
            else:
                connection.execute(
                    """
                    INSERT INTO posts (
                        slug, title, excerpt, published_at, created_at, updated_at,
                        read_time, category, featured, tone, tags, hero_quote,
                        cover_image, sections, markdown_content, html_content, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (slug, title, excerpt, published_at, now, now, read_time, category, featured, tone, tags_json,
                     hero_quote, cover_image, sections, markdown_content, html_content, status),
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
        label: str = "文件",
    ) -> str:
        original_filename = (file_storage.filename or "file").strip()
        if folder in PUBLIC_UPLOAD_FOLDERS:
            raw_bytes = validate_image_upload(file_storage, max_bytes=self.max_image_bytes, max_pixels=self.max_image_pixels)
        else:
            if allowed_extensions:
                validate_extension(original_filename, allowed_extensions, label)
            stream = file_storage.stream
            stream.seek(0)
            raw_bytes = stream.read(self.max_file_bytes + 1)
            stream.seek(0)
            if len(raw_bytes) > self.max_file_bytes:
                raise ValueError(f"{label}过大，请控制在 {self.max_file_bytes // (1024 * 1024)} MB 以内。")

        source_path = Path(original_filename)
        suffix = source_path.suffix.lower()
        safe_stem = secure_filename(source_path.stem) or "file"
        unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{safe_stem}{suffix}"
        relative_path = Path(folder) / unique_name
        destination = UPLOADS_DIR / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw_bytes)
        return relative_path.as_posix()

    def import_markdown(self, file_storage) -> dict[str, Any]:
        validate_extension(file_storage.filename or "", ALLOWED_MARKDOWN_EXTENSIONS, "Markdown 文件")
        content = decode_markdown_file(file_storage.read())
        metadata, markdown_content = parse_markdown_front_matter(content)

        guessed_title = str(metadata.get("title") or "").strip()
        if not guessed_title:
            for line in markdown_content.splitlines():
                if line.startswith("# "):
                    guessed_title = line[2:].strip()
                    break

        tags = metadata.get("tags") if isinstance(metadata.get("tags"), list) else []
        excerpt = str(metadata.get("excerpt") or "").strip() or self.build_excerpt(markdown_content)
        requested_slug = str(metadata.get("slug") or "").strip()
        return {
            "title": guessed_title,
            "slug": requested_slug or (slugify(guessed_title) if guessed_title else ""),
            "tags": tags,
            "tags_text": ", ".join(tags),
            "category": str(metadata.get("category") or "").strip(),
            "published_at": str(metadata.get("date") or "").strip(),
            "cover_image": str(metadata.get("cover") or "").strip(),
            "excerpt": excerpt,
            "hero_quote": str(metadata.get("hero_quote") or "").strip(),
            "markdown_content": markdown_content,
            "html_content": render_markdown(markdown_content),
            "read_time": estimate_read_time(markdown_content),
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




