from __future__ import annotations

import difflib
import html
import io
import json
import math
import os
import re
import sqlite3
import uuid
from datetime import date, datetime, timedelta
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
ALLOWED_MARKDOWN_EXTENSIONS = {".md", ".markdown", ".txt"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".jfif"}
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
    "status, click_count, deleted_at"
)
ADMIN_LIST_LIMIT = 200
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
MEDIA_URL_PATTERN = re.compile(r"/uploads/media/([^\s)\]\"\'<>?#]+)", re.IGNORECASE)


def _markdown_has_unclosed_fence(markdown_content: str) -> bool:
    fence_count = sum(1 for line in str(markdown_content or "").splitlines() if re.match(r"^\s*```", line))
    return fence_count % 2 == 1


def _markdown_has_heading_space_issue(markdown_content: str) -> bool:
    return bool(re.search(r"(?:^|\n)#{1,6}[^#\s\n]", str(markdown_content or "")))


def _markdown_has_section_heading(markdown_content: str) -> bool:
    return bool(re.search(r"(?:^|\n)##\s+\S", str(markdown_content or "")))


MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[\"\'][^)]*[\"\'])?\)")


def _markdown_images(markdown_content: str) -> list[tuple[str, str]]:
    return [
        (match.group(1).strip(), match.group(2).strip())
        for match in MARKDOWN_IMAGE_PATTERN.finditer(str(markdown_content or ""))
    ]


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
    # Rich-text paste often carries NBSP (U+00A0) indentation; rendered code
    # copied back out would then fail to run, so normalize before rendering.
    rendered = markdown_lib.markdown(
        (markdown_text or "").replace("\xa0", " "),
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



MAX_IMAGE_EDGE = 1920
JPEG_RECODE_QUALITY = 85


def process_uploaded_image_bytes(raw_bytes: bytes) -> bytes:
    """Downscale large raster images and strip JPEG EXIF/GPS via re-encode."""
    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            image_format = (image.format or "").upper()
            if image_format not in {"JPEG", "PNG", "WEBP"}:
                return raw_bytes
            image.load()
            working = image
            original_size = working.size
            if image_format == "JPEG" and working.mode not in {"RGB", "L"}:
                working = working.convert("RGB")
            needs_resize = max(original_size) > MAX_IMAGE_EDGE
            if needs_resize:
                working = working.copy()
                working.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
            # JPEG always re-encoded to drop EXIF/GPS even when dimensions stay.
            if image_format == "JPEG" or needs_resize:
                output = io.BytesIO()
                save_kwargs: dict[str, Any] = {"format": image_format, "optimize": True}
                if image_format in {"JPEG", "WEBP"}:
                    save_kwargs["quality"] = JPEG_RECODE_QUALITY
                working.save(output, **save_kwargs)
                return output.getvalue()
            return raw_bytes
    except (UnidentifiedImageError, OSError, ValueError):
        return raw_bytes


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






def strip_leading_title_heading(markdown_content: str, title: str = "") -> str:
    """Remove a first ATX H1 when it duplicates the article title field."""
    text = (markdown_content or "").lstrip("﻿")
    lines = text.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines):
        return markdown_content
    match = re.match(r"^#\s+(.+?)\s*$", lines[index])
    if not match:
        return markdown_content
    heading = match.group(1).strip()
    normalized_title = re.sub(r"\s+", " ", (title or "").strip())
    normalized_heading = re.sub(r"\s+", " ", heading)
    if normalized_title and normalized_heading != normalized_title:
        return markdown_content
    remaining = lines[:index] + lines[index + 1 :]
    while remaining and not remaining[0].strip():
        remaining = remaining[1:]
    joined = "\n".join(remaining).strip()
    return (joined + "\n") if joined else ""


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

            CREATE TABLE IF NOT EXISTS post_working_copies (
                post_id INTEGER PRIMARY KEY,
                base_post_updated_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS media_metadata (
                path TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_posts_status_pub_order
            ON posts (status, published_at DESC, updated_at DESC, id DESC);

            CREATE INDEX IF NOT EXISTS idx_post_revisions_post_created
            ON post_revisions (post_id, created_at DESC, id DESC);
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

            CREATE TABLE IF NOT EXISTS post_working_copies (
                post_id INTEGER PRIMARY KEY,
                base_post_updated_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS media_metadata (
                path TEXT PRIMARY KEY,
                original_filename TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_posts_status_pub_order
            ON posts (status, published_at DESC, updated_at DESC, id DESC);
            CREATE INDEX IF NOT EXISTS idx_post_revisions_post_created
            ON post_revisions (post_id, created_at DESC, id DESC);
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
            working_rows = connection.execute(
                "SELECT post_id, snapshot_json, updated_at, version FROM post_working_copies"
            ).fetchall()
        working_map: dict[int, dict[str, Any]] = {}
        for row in working_rows:
            try:
                snapshot = json.loads(row["snapshot_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                snapshot = {}
            working_map[int(row["post_id"])] = {
                "snapshot": snapshot,
                "updated_at": row["updated_at"],
                "version": int(row["version"]),
            }
        items = [self._row_to_dict(row) for row in rows]
        for item in items:
            working = working_map.get(int(item["id"]))
            item["pending_changes"] = working is not None
            item["working_copy_version"] = working.get("version") if working else None
            item["effective_updated_at"] = working.get("updated_at") if working else item.get("updated_at")
            pending_snapshot = (working.get("snapshot") or {}) if working else {}
            pending_title = pending_snapshot.get("title")
            item["display_title"] = pending_title or item.get("title") or "\u65e0\u6807\u9898\u8349\u7a3f"
            if working:
                for field in ("category", "tags", "cover_image", "published_at", "read_time", "excerpt", "slug"):
                    if field in pending_snapshot:
                        item[field] = pending_snapshot.get(field)
        items.sort(
            key=lambda item: (str(item.get("effective_updated_at") or ""), int(item.get("id") or 0)),
            reverse=True,
        )
        return items[:capped]

    def author_attention_items(self, *, limit: int = 8) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for summary in self.list_admin_posts():
            if summary.get("status") == "trashed":
                continue
            post = self.get_post_by_id(int(summary["id"])) or {}
            working = self.get_working_copy(int(summary["id"])) if summary.get("pending_changes") else None
            source = working.get("snapshot") if working else post
            fields = self._snapshot_as_form(source)
            validation = self.validate_post_for_publish(fields, post_id=int(summary["id"]))
            reasons: list[str] = []
            if summary.get("pending_changes"):
                reasons.append("\u6709\u5f85\u53d1\u5e03\u4fee\u6539")
            if not str(source.get("title") or "").strip():
                reasons.append("\u65e0\u6807\u9898\u8349\u7a3f")
            if validation["errors"]:
                reasons.append(f"{len(validation['errors'])} \u4e2a\u53d1\u5e03\u9519\u8bef")
            if validation["warnings"]:
                reasons.append(f"{len(validation['warnings'])} \u6761\u53d1\u5e03\u63d0\u9192")
            if not reasons:
                continue
            items.append({
                "id": summary["id"],
                "title": summary.get("display_title") or "\u65e0\u6807\u9898\u8349\u7a3f",
                "status": summary.get("status"),
                "pending_changes": bool(summary.get("pending_changes")),
                "updated_at": summary.get("effective_updated_at") or summary.get("updated_at"),
                "reasons": reasons,
            })
        return items[:max(1, int(limit))]

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
        if cover_image and not _is_safe_image_url(cover_image):
            add(errors, "invalid_cover", "cover_image", '封面图片必须是 /uploads/ 地址或 http(s) 图片链接。')
        if len(tags) > 40:
            add(errors, "too_many_tags", "tags", '标签数量不能超过 40 个。')
        if any(len(item) > 80 for item in tags):
            add(errors, "tag_too_long", "tags", '单个标签不能超过 80 个字符。')
        if _markdown_has_unclosed_fence(markdown_content):
            add(errors, "unclosed_code_fence", "markdown_content", '检测到未闭合的 ``` 代码围栏。')
        if _markdown_has_heading_space_issue(markdown_content):
            add(errors, "invalid_heading", "markdown_content", 'Markdown 标题 # 后需要空格。')

        if not excerpt:
            add(warnings, "missing_excerpt", "excerpt", '未填写摘要，发布时将自动生成。')
        if not category:
            add(warnings, "missing_category", "category", '建议填写文章分类，方便前台组织内容。')
        if not tags:
            add(warnings, "missing_tags", "tags", '建议至少填写一个标签。')
        if not cover_image:
            add(warnings, "missing_cover", "cover_image", '未设置封面图，前台将使用文字卡片。')
        if markdown_content and not _markdown_has_section_heading(markdown_content):
            add(warnings, "missing_sections", "markdown_content", '正文没有二级标题，前台不会显示目录。')
        if raw_slug and re.search(r"[^\x00-\x7f]", raw_slug):
            add(warnings, "non_ascii_slug", "slug", 'Slug 包含中文或特殊字符，分享链接会被编码。')
        if markdown_content and len(re.sub(r"\s+", "", markdown_content)) < 200:
            add(warnings, "short_content", "markdown_content", '正文较短，请确认内容已经完整。')

        images = _markdown_images(markdown_content)
        empty_alt_count = sum(
            1 for alt, _url in images
            if not alt or alt.lower() in {"image", "img", "\u56fe\u7247"}
        )
        if empty_alt_count:
            add(warnings, "missing_image_alt", "markdown_content", f"\u6709 {empty_alt_count} \u5f20\u6b63\u6587\u56fe\u7247\u7f3a\u5c11\u6709\u610f\u4e49\u7684\u66ff\u4ee3\u6587\u672c\u3002")
        missing_local_images = []
        for _alt, url in images:
            clean_url = unquote(url.split("?", 1)[0].split("#", 1)[0])
            if clean_url.startswith("/uploads/media/"):
                candidate = UPLOADS_DIR / "media" / Path(clean_url).name
                if not candidate.is_file():
                    missing_local_images.append(clean_url)
        if missing_local_images:
            add(errors, "missing_local_image", "markdown_content", f'\u6b63\u6587\u5f15\u7528\u4e86 {len(missing_local_images)} \u5f20\u4e0d\u5b58\u5728\u7684\u672c\u5730\u56fe\u7247\u3002')

        normalized_slug = slugify(raw_slug or title) if title or raw_slug else ""
        return {
            "ok": not errors,
            "errors": errors,
            "warnings": warnings,
            "normalized": {
                "slug": normalized_slug,
                "excerpt": excerpt or self.build_excerpt(markdown_content),
                "read_time": estimate_read_time(markdown_content),
            },
        }

    @staticmethod
    def _revision_snapshot_from_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
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

    def _insert_revision_snapshot(
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

    def _insert_revision(
        self,
        connection: sqlite3.Connection,
        post_id: int,
        revision_type: str,
    ) -> int:
        row = connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if row is None:
            raise ValueError("\u7a3f\u4ef6\u4e0d\u5b58\u5728\u3002")
        return self._insert_revision_snapshot(
            connection, post_id, revision_type, self._revision_snapshot_from_row(row)
        )

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
            raise ValueError("\u6807\u7b7e\u6570\u91cf\u8fc7\u591a\uff0c\u8bf7\u63a7\u5236\u5728 40 \u4e2a\u4ee5\u5185\u3002")
        cover_image = validate_text_length(
            "cover_image", form_data.get("cover_image", fallback.get("cover_image", ""))
        )
        if cover_image and not _is_safe_image_url(cover_image):
            raise ValueError("\u5c01\u9762\u56fe\u7247\u5730\u5740\u65e0\u6548\u3002")
        return {
            "title": title,
            "slug": validate_text_length("slug", form_data.get("slug", fallback.get("slug", ""))),
            "excerpt": excerpt or self.build_excerpt(markdown_content),
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

    def get_working_copy(self, post_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM post_working_copies WHERE post_id = ?", (post_id,)
            ).fetchone()
        if row is None:
            return None
        try:
            snapshot = json.loads(row["snapshot_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            snapshot = {}
        snapshot["html_content"] = render_markdown(str(snapshot.get("markdown_content") or ""))
        return {
            "post_id": row["post_id"],
            "base_post_updated_at": row["base_post_updated_at"],
            "version": int(row["version"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "snapshot": snapshot,
        }

    def save_working_copy(
        self,
        post_id: int,
        form_data: dict[str, Any],
        *,
        expected_version: int | None = None,
        expected_base_updated_at: str | None = None,
    ) -> dict[str, Any]:
        live_post = self.get_post_by_id(post_id)
        if live_post is None:
            raise ValueError("\u7a3f\u4ef6\u4e0d\u5b58\u5728\u3002")
        if live_post.get("status") != "published":
            raise ValueError("\u53ea\u6709\u5df2\u53d1\u5e03\u6587\u7ae0\u4f7f\u7528\u5de5\u4f5c\u526f\u672c\u3002")
        snapshot = self._normalize_edit_snapshot(form_data, fallback=live_post)
        now = datetime.now().isoformat(timespec="microseconds")
        with self.connect() as connection:
            current = connection.execute(
                "SELECT updated_at, status FROM posts WHERE id = ?", (post_id,)
            ).fetchone()
            if current is None or current["status"] != "published":
                raise PostVersionConflict("\u7ebf\u4e0a\u6587\u7ae0\u72b6\u6001\u5df2\u53d8\u5316\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u3002")
            existing = connection.execute(
                "SELECT * FROM post_working_copies WHERE post_id = ?", (post_id,)
            ).fetchone()
            if existing is None:
                if expected_base_updated_at and current["updated_at"] != expected_base_updated_at:
                    raise PostVersionConflict("\u7ebf\u4e0a\u6587\u7ae0\u5df2\u66f4\u65b0\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u3002")
                version = 1
                connection.execute(
                    """
                    INSERT INTO post_working_copies (
                        post_id, base_post_updated_at, snapshot_json, version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (post_id, current["updated_at"], json.dumps(snapshot, ensure_ascii=False), version, now, now),
                )
            else:
                if expected_version is None or int(expected_version) != int(existing["version"]):
                    raise PostVersionConflict("\u5f85\u53d1\u5e03\u4fee\u6539\u5df2\u5728\u5176\u4ed6\u9875\u9762\u66f4\u65b0\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u3002")
                if current["updated_at"] != existing["base_post_updated_at"]:
                    raise PostVersionConflict("\u7ebf\u4e0a\u7248\u672c\u5df2\u53d8\u5316\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u3002")
                version = int(existing["version"]) + 1
                connection.execute(
                    """
                    UPDATE post_working_copies
                    SET snapshot_json = ?, version = ?, updated_at = ?
                    WHERE post_id = ?
                    """,
                    (json.dumps(snapshot, ensure_ascii=False), version, now, post_id),
                )
            connection.commit()
        return self.get_working_copy(post_id) or {}

    def discard_working_copy(self, post_id: int, *, archive: bool = True) -> bool:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT snapshot_json FROM post_working_copies WHERE post_id = ?", (post_id,)
            ).fetchone()
            if row is None:
                return False
            if archive:
                try:
                    snapshot = json.loads(row["snapshot_json"] or "{}")
                except (TypeError, json.JSONDecodeError):
                    snapshot = {}
                snapshot["html_content"] = render_markdown(str(snapshot.get("markdown_content") or ""))
                snapshot["status"] = "draft"
                self._insert_revision_snapshot(connection, post_id, "discarded_changes", snapshot)
            connection.execute("DELETE FROM post_working_copies WHERE post_id = ?", (post_id,))
            connection.commit()
        return True

    def create_checkpoint(self, post_id: int) -> int:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                raise ValueError("\u7a3f\u4ef6\u4e0d\u5b58\u5728\u3002")
            copy_row = connection.execute(
                "SELECT snapshot_json FROM post_working_copies WHERE post_id = ?", (post_id,)
            ).fetchone()
            if copy_row is not None:
                snapshot = json.loads(copy_row["snapshot_json"] or "{}")
                snapshot["html_content"] = render_markdown(str(snapshot.get("markdown_content") or ""))
                snapshot["status"] = "draft"
            else:
                snapshot = self._revision_snapshot_from_row(row)
            revision_id = self._insert_revision_snapshot(connection, post_id, "checkpoint", snapshot)
            connection.commit()
        return revision_id

    @staticmethod
    def _snapshot_as_form(snapshot: dict[str, Any]) -> dict[str, Any]:
        result = {field: snapshot.get(field, "") for field in POST_EDIT_FIELDS}
        tags = snapshot.get("tags", [])
        result["tags"] = ", ".join(tags) if isinstance(tags, list) else str(tags or "")
        return result

    def _prepare_snapshot_for_post(
        self,
        source: dict[str, Any],
        *,
        fallback: dict[str, Any],
        post_id: int,
    ) -> dict[str, Any]:
        snapshot = self._normalize_edit_snapshot(source, fallback=fallback)
        desired_slug = snapshot.get("slug") or snapshot.get("title") or fallback.get("slug") or f"draft-{uuid.uuid4().hex[:12]}"
        snapshot["slug"] = self.ensure_unique_slug(str(desired_slug), post_id=post_id)
        return snapshot

    @staticmethod
    def _update_post_from_snapshot(
        connection: sqlite3.Connection,
        post_id: int,
        snapshot: dict[str, Any],
        *,
        status: str,
        updated_at: str,
        deleted_at: str | None = None,
    ) -> None:
        tags = snapshot.get("tags") if isinstance(snapshot.get("tags"), list) else []
        markdown_content = str(snapshot.get("markdown_content") or "")
        connection.execute(
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

    def unpublish_post(self, post_id: int) -> dict[str, Any]:
        post = self.get_post_by_id(post_id)
        if post is None:
            raise ValueError("\u6587\u7ae0\u4e0d\u5b58\u5728\u3002")
        if post.get("status") != "published":
            raise ValueError("\u53ea\u6709\u5df2\u53d1\u5e03\u6587\u7ae0\u53ef\u4ee5\u4e0b\u67b6\u3002")
        working = self.get_working_copy(post_id)
        working_version = working.get("version") if working else None
        snapshot = self._prepare_snapshot_for_post(
            working.get("snapshot") if working else post,
            fallback=post,
            post_id=post_id,
        )
        now = datetime.now().isoformat(timespec="microseconds")
        with self.connect() as connection:
            current = connection.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if current is None or current["status"] != "published":
                raise PostVersionConflict("\u6587\u7ae0\u72b6\u6001\u5df2\u53d8\u5316\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u3002")
            if working_version is not None:
                current_copy = connection.execute(
                    "SELECT version FROM post_working_copies WHERE post_id = ?", (post_id,)
                ).fetchone()
                if current_copy is None or int(current_copy["version"]) != int(working_version):
                    raise PostVersionConflict("\u5f85\u53d1\u5e03\u4fee\u6539\u5df2\u66f4\u65b0\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u3002")
            self._insert_revision(connection, post_id, "pre_unpublish")
            self._update_post_from_snapshot(
                connection, post_id, snapshot, status="draft", updated_at=now, deleted_at=None
            )
            connection.execute("DELETE FROM post_working_copies WHERE post_id = ?", (post_id,))
            self._insert_revision(connection, post_id, "unpublished")
            connection.commit()
        return self.get_post_by_id(post_id) or {}

    def save_post(
        self,
        form_data: dict[str, Any],
        *,
        post_id: int | None = None,
        action: str = "draft",
        expected_updated_at: str | None = None,
        expected_working_version: int | None = None,
        create_revision: bool = True,
        allow_untitled: bool = False,
    ) -> int:
        if action not in {"draft", "published"}:
            raise ValueError('文章状态无效。')
        if action == "published":
            validation = self.validate_post_for_publish(form_data, post_id=post_id)
            if validation["errors"]:
                raise ValueError(validation["errors"][0]["message"])

        title = validate_text_length("title", form_data.get("title", ""))
        if not title and not allow_untitled:
            raise ValueError('文章标题不能为空。')
        markdown_content = validate_text_length("markdown_content", form_data.get("markdown_content", ""))
        html_content = render_markdown(markdown_content)
        excerpt = validate_text_length("excerpt", form_data.get("excerpt", "")) or self.build_excerpt(markdown_content)
        raw_slug = validate_text_length("slug", form_data.get("slug", ""))
        existing_for_slug = self.get_post_by_id(post_id) if post_id else None
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
        slug = self.ensure_unique_slug(desired_slug, post_id=post_id)
        published = action == "published"
        status = "published" if published else "draft"
        published_at = validate_text_length("published_at", form_data.get("published_at", ""))
        if published and not published_at:
            published_at = date.today().isoformat()

        tags_text = validate_text_length("tags", form_data.get("tags", ""))
        tags = [validate_text_length("tag", item, max_length=80) for item in tags_text.split(",") if item.strip()]
        if len(tags) > 40:
            raise ValueError('标签数量过多，请控制在 40 个以内。')
        featured = 0
        read_time = validate_text_length("read_time", form_data.get("read_time", "")) or estimate_read_time(markdown_content)
        category = validate_text_length("category", form_data.get("category", ""))
        tone = "amber"
        hero_quote = validate_text_length("hero_quote", form_data.get("hero_quote", ""))
        cover_image = validate_text_length("cover_image", form_data.get("cover_image", ""))
        if cover_image and not _is_safe_image_url(cover_image):
            raise ValueError('封面图片地址无效：请使用上传得到的 /uploads/ 地址或 http(s) 图片链接。')
        sections = json.dumps([], ensure_ascii=False)
        tags_json = json.dumps(tags, ensure_ascii=False)
        now = datetime.now().isoformat(timespec="microseconds")

        with self.connect() as connection:
            previous_status = ""
            if post_id:
                current_row = connection.execute("SELECT updated_at, status FROM posts WHERE id = ?", (post_id,)).fetchone()
                if current_row is None:
                    raise ValueError('稿件不存在。')
                previous_status = current_row["status"] or "draft"
                working_row = connection.execute(
                    "SELECT base_post_updated_at, version FROM post_working_copies WHERE post_id = ?",
                    (post_id,),
                ).fetchone()
                if action == "published" and previous_status == "published" and working_row is not None:
                    if expected_working_version is None or int(expected_working_version) != int(working_row["version"]):
                        raise PostVersionConflict("\u5f85\u53d1\u5e03\u4fee\u6539\u5df2\u5728\u5176\u4ed6\u9875\u9762\u66f4\u65b0\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u540e\u518d\u53d1\u5e03\u3002")
                    if current_row["updated_at"] != working_row["base_post_updated_at"]:
                        raise PostVersionConflict("\u7ebf\u4e0a\u7248\u672c\u5df2\u53d8\u5316\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u540e\u518d\u53d1\u5e03\u3002")
                if action == "published" and previous_status == "published":
                    self._insert_revision(connection, post_id, "pre_publish")
                if expected_updated_at is not None and current_row["updated_at"] != expected_updated_at:
                    raise PostVersionConflict('文章已在其他页面更新，请重新加载后再保存。')
                connection.execute(
                    """
                    UPDATE posts
                    SET slug = ?, title = ?, excerpt = ?, published_at = ?, updated_at = ?,
                        read_time = ?, category = ?, featured = ?, tone = ?, tags = ?,
                        hero_quote = ?, cover_image = ?, sections = ?, markdown_content = ?,
                        html_content = ?, status = ?, deleted_at = NULL
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
                        cover_image, sections, markdown_content, html_content, status, deleted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (slug, title, excerpt, published_at, now, now, read_time, category, featured, tone, tags_json,
                     hero_quote, cover_image, sections, markdown_content, html_content, status),
                )
                saved_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])

            if create_revision:
                if not post_id:
                    revision_type = "created"
                elif action == "published":
                    revision_type = "published"
                elif previous_status == "published":
                    revision_type = "unpublished"
                else:
                    revision_type = "draft_saved"
                self._insert_revision(connection, saved_id, revision_type)
            if action == "published":
                connection.execute("DELETE FROM post_working_copies WHERE post_id = ?", (saved_id,))
            connection.commit()
        return saved_id

    def trash_post(self, post_id: int) -> None:
        post = self.get_post_by_id(post_id)
        if post is None:
            raise ValueError("\u6587\u7ae0\u4e0d\u5b58\u5728\u6216\u5df2\u7ecf\u88ab\u5220\u9664\u3002")
        if post.get("status") == "trashed":
            raise ValueError("\u6587\u7ae0\u5df2\u7ecf\u5728\u56de\u6536\u7ad9\u4e2d\u3002")
        working = self.get_working_copy(post_id)
        working_version = working.get("version") if working else None
        snapshot = self._prepare_snapshot_for_post(
            working.get("snapshot") if working else post,
            fallback=post,
            post_id=post_id,
        )
        now = datetime.now().isoformat(timespec="microseconds")
        with self.connect() as connection:
            current = connection.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if current is None or current["status"] == "trashed":
                raise PostVersionConflict("\u6587\u7ae0\u72b6\u6001\u5df2\u53d8\u5316\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u3002")
            if working_version is not None:
                current_copy = connection.execute(
                    "SELECT version FROM post_working_copies WHERE post_id = ?", (post_id,)
                ).fetchone()
                if current_copy is None or int(current_copy["version"]) != int(working_version):
                    raise PostVersionConflict("\u5f85\u53d1\u5e03\u4fee\u6539\u5df2\u66f4\u65b0\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u3002")
            self._insert_revision(connection, post_id, "pre_trash")
            self._update_post_from_snapshot(
                connection, post_id, snapshot, status="trashed", updated_at=now, deleted_at=now
            )
            connection.execute("DELETE FROM post_working_copies WHERE post_id = ?", (post_id,))
            self._insert_revision(connection, post_id, "trashed")
            connection.commit()

    def delete_post(self, post_id: int) -> None:
        self.trash_post(post_id)

    def restore_post(self, post_id: int) -> None:
        now = datetime.now().isoformat(timespec="microseconds")
        with self.connect() as connection:
            row = connection.execute("SELECT status FROM posts WHERE id = ?", (post_id,)).fetchone()
            if row is None:
                raise ValueError('文章不存在。')
            if row["status"] != "trashed":
                raise ValueError('只有回收站中的文章可以恢复。')
            connection.execute(
                "UPDATE posts SET status = 'draft', deleted_at = NULL, updated_at = ? WHERE id = ?",
                (now, post_id),
            )
            self._insert_revision(connection, post_id, "restored_from_trash")
            connection.commit()

    def purge_expired_trash(self, *, retention_days: int = 30, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now()) - timedelta(days=max(1, retention_days))
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM posts WHERE status = 'trashed' AND deleted_at IS NOT NULL AND deleted_at <= ?",
                (cutoff.isoformat(timespec="microseconds"),),
            )
            connection.commit()
        return max(0, int(cursor.rowcount or 0))

    def list_post_revisions(self, post_id: int) -> list[dict[str, Any]]:
        if self.get_post_by_id(post_id) is None:
            raise ValueError('稿件不存在。')
        with self.connect() as connection:
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

    def get_post_revision(self, post_id: int, revision_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
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
        markdown_content = str(snapshot.get("markdown_content") or "")
        snapshot["html_content"] = render_markdown(markdown_content)
        return {
            "id": row["id"],
            "post_id": row["post_id"],
            "revision_type": row["revision_type"],
            "created_at": row["created_at"],
            "snapshot": snapshot,
        }

    def restore_post_revision(self, post_id: int, revision_id: int) -> dict[str, Any]:
        revision = self.get_post_revision(post_id, revision_id)
        if revision is None:
            raise ValueError('历史版本不存在。')
        snapshot = revision["snapshot"]
        title = validate_text_length("title", snapshot.get("title", ""))
        markdown_content = validate_text_length("markdown_content", snapshot.get("markdown_content", ""))
        if not title:
            raise ValueError('历史版本缺少文章标题，无法恢复。')
        current_post = self.get_post_by_id(post_id)
        if current_post is None:
            raise ValueError("\u7a3f\u4ef6\u4e0d\u5b58\u5728\u3002")
        if current_post.get("status") == "published":
            working = self.get_working_copy(post_id)
            restored = self.save_working_copy(
                post_id,
                self._snapshot_as_form(snapshot),
                expected_version=working.get("version") if working else None,
                expected_base_updated_at=current_post.get("updated_at"),
            )
            archived = dict(snapshot)
            archived["html_content"] = render_markdown(markdown_content)
            archived["status"] = "draft"
            with self.connect() as connection:
                self._insert_revision_snapshot(
                    connection, post_id, "restored_to_working_copy", archived
                )
                connection.commit()
            return {
                **current_post,
                **restored.get("snapshot", {}),
                "status": "published",
                "pending_changes": True,
                "working_copy_version": restored.get("version"),
            }
        tags = snapshot.get("tags") if isinstance(snapshot.get("tags"), list) else []
        tags = [validate_text_length("tag", item, max_length=80) for item in tags[:40]]
        cover_image = validate_text_length("cover_image", snapshot.get("cover_image", ""))
        if cover_image and not _is_safe_image_url(cover_image):
            cover_image = ""
        # Restore must not resurrect a slug now owned by another post (slug is UNIQUE).
        slug = self.ensure_unique_slug(
            validate_text_length("slug", snapshot.get("slug", "")) or title,
            post_id=post_id,
        )
        now = datetime.now().isoformat(timespec="microseconds")
        with self.connect() as connection:
            current = connection.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
            if current is None:
                raise ValueError('稿件不存在。')
            self._insert_revision(connection, post_id, "pre_restore")
            connection.execute(
                """
                UPDATE posts
                SET title = ?, slug = ?, excerpt = ?, published_at = ?, read_time = ?,
                    category = ?, tags = ?, hero_quote = ?, cover_image = ?,
                    markdown_content = ?, html_content = ?, status = 'draft',
                    deleted_at = NULL, updated_at = ?
                WHERE id = ?
                """,
                (
                    title,
                    slug,
                    validate_text_length("excerpt", snapshot.get("excerpt", "")) or self.build_excerpt(markdown_content),
                    validate_text_length("published_at", snapshot.get("published_at", "")),
                    validate_text_length("read_time", snapshot.get("read_time", "")) or estimate_read_time(markdown_content),
                    validate_text_length("category", snapshot.get("category", "")),
                    json.dumps(tags, ensure_ascii=False),
                    validate_text_length("hero_quote", snapshot.get("hero_quote", "")),
                    cover_image,
                    markdown_content,
                    render_markdown(markdown_content),
                    now,
                    post_id,
                ),
            )
            self._insert_revision(connection, post_id, "restored")
            connection.commit()
        return self.get_post_by_id(post_id) or {}

    def compare_post_versions(self, post_id: int, left: str = "live", right: str = "working") -> dict[str, Any]:
        post = self.get_post_by_id(post_id)
        if post is None:
            raise ValueError("\u7a3f\u4ef6\u4e0d\u5b58\u5728\u3002")

        def resolve(selector: str) -> tuple[str, dict[str, Any]]:
            if selector in {"live", "current"}:
                return ("\u7ebf\u4e0a\u7248\u672c" if post.get("status") == "published" else "\u5f53\u524d\u8349\u7a3f", post)
            if selector == "working":
                working = self.get_working_copy(post_id)
                if working is None:
                    return ("\u5f53\u524d\u7f16\u8f91\u5185\u5bb9", post)
                return ("\u5f85\u53d1\u5e03\u4fee\u6539", working.get("snapshot") or {})
            try:
                revision_id = int(selector)
            except (TypeError, ValueError):
                raise ValueError("\u7248\u672c\u9009\u62e9\u65e0\u6548\u3002")
            revision = self.get_post_revision(post_id, revision_id)
            if revision is None:
                raise ValueError("\u5386\u53f2\u7248\u672c\u4e0d\u5b58\u5728\u3002")
            return (f"Revision {revision_id}", revision.get("snapshot") or {})

        left_label, left_snapshot = resolve(left)
        right_label, right_snapshot = resolve(right)
        field_changes = []
        for field in ("title", "slug", "excerpt", "published_at", "read_time", "category", "tags", "hero_quote", "cover_image"):
            before = left_snapshot.get(field, "")
            after = right_snapshot.get(field, "")
            if before != after:
                field_changes.append({"field": field, "before": before, "after": after})
        before_lines = str(left_snapshot.get("markdown_content") or "").splitlines()
        after_lines = str(right_snapshot.get("markdown_content") or "").splitlines()
        markdown_diff = list(difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=left_label,
            tofile=right_label,
            lineterm="",
        ))
        return {
            "left": {"selector": left, "label": left_label},
            "right": {"selector": right, "label": right_label},
            "field_changes": field_changes,
            "markdown_diff": markdown_diff,
            "changed": bool(field_changes or markdown_diff),
        }

    def list_media_assets(self) -> list[dict[str, Any]]:
        media_dir = UPLOADS_DIR / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        references: dict[str, list[dict[str, Any]]] = {}
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, title, slug, status, cover_image, markdown_content FROM posts"
            ).fetchall()
            working_rows = connection.execute(
                """
                SELECT p.id, p.title, p.slug, w.snapshot_json
                FROM post_working_copies w
                JOIN posts p ON p.id = w.post_id
                """
            ).fetchall()
            media_names = {
                str(row["path"]): str(row["original_filename"] or "")
                for row in connection.execute(
                    "SELECT path, original_filename FROM media_metadata"
                ).fetchall()
            }
        for row in rows:
            found: set[tuple[str, str]] = set()
            cover_url = str(row["cover_image"] or "")
            if cover_url.startswith("/uploads/media/"):
                found.add((unquote(cover_url.split("?", 1)[0].split("#", 1)[0]), "cover"))
            for match in MEDIA_URL_PATTERN.finditer(str(row["markdown_content"] or "")):
                found.add(("/uploads/media/" + unquote(match.group(1)), "body"))
            for url, kind in found:
                references.setdefault(url, []).append({
                    "post_id": row["id"],
                    "title": row["title"],
                    "slug": row["slug"],
                    "status": row["status"],
                    "kind": kind,
                })

        for row in working_rows:
            try:
                snapshot = json.loads(row["snapshot_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                snapshot = {}
            found: set[tuple[str, str]] = set()
            cover_url = str(snapshot.get("cover_image") or "")
            if cover_url.startswith("/uploads/media/"):
                found.add((unquote(cover_url.split("?", 1)[0].split("#", 1)[0]), "working_cover"))
            for match in MEDIA_URL_PATTERN.finditer(str(snapshot.get("markdown_content") or "")):
                found.add(("/uploads/media/" + unquote(match.group(1)), "working_body"))
            for url, kind in found:
                references.setdefault(url, []).append({
                    "post_id": row["id"],
                    "title": snapshot.get("title") or row["title"] or "\u65e0\u6807\u9898\u8349\u7a3f",
                    "slug": snapshot.get("slug") or row["slug"],
                    "status": "working_copy",
                    "kind": kind,
                })

        assets: list[dict[str, Any]] = []
        for path in media_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in UPLOAD_IMAGE_EXTENSIONS:
                continue
            stat = path.stat()
            width = 0
            height = 0
            try:
                with Image.open(path) as image:
                    width, height = image.size
            except (UnidentifiedImageError, OSError, ValueError):
                pass
            url = "/uploads/media/" + path.name
            refs = references.get(url, [])
            fallback_name = re.sub(r"^(?:\d{20}-)+", "", path.name) or path.name
            assets.append({
                "url": url,
                "filename": path.name,
                "original_filename": media_names.get(f"media/{path.name}", "") or fallback_name,
                "size": stat.st_size,
                "width": width,
                "height": height,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "references": refs,
                "reference_count": len(refs),
            })
        assets.sort(key=lambda item: (item["created_at"], item["filename"]), reverse=True)
        return assets

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
            raw_bytes = process_uploaded_image_bytes(raw_bytes)
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
        relative_text = relative_path.as_posix()
        if folder == "media":
            now = datetime.now().isoformat(timespec="microseconds")
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO media_metadata (path, original_filename, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET original_filename = excluded.original_filename
                    """,
                    (relative_text, original_filename, now),
                )
                connection.commit()
        return relative_text

    def import_markdown(self, file_storage) -> dict[str, Any]:
        validate_extension(file_storage.filename or "", ALLOWED_MARKDOWN_EXTENSIONS, "Markdown 文件")
        content = decode_markdown_file(file_storage.read()).replace("\xa0", " ")
        metadata, markdown_content = parse_markdown_front_matter(content)

        guessed_title = str(metadata.get("title") or "").strip()
        if not guessed_title:
            for line in markdown_content.splitlines():
                if line.startswith("# "):
                    guessed_title = line[2:].strip()
                    break

        markdown_content = strip_leading_title_heading(markdown_content, guessed_title)

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
            allowed_extensions=UPLOAD_IMAGE_EXTENSIONS,
            label="图片",
        )
        return {
            "path": relative_path,
            "url": "/uploads/" + relative_path,
            "filename": Path(relative_path).name,
            "original_filename": (file_storage.filename or Path(relative_path).name).strip(),
        }

    def list_taxonomy(self) -> dict[str, list[str]]:
        with self.connect() as connection:
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

    def content_health(self) -> dict[str, Any]:
        active = [item for item in self.list_admin_posts() if item.get("status") != "trashed"]
        without_sections = 0
        missing_images = 0
        empty_alt = 0
        for item in active:
            post = self.get_post_by_id(int(item["id"])) or {}
            working = self.get_working_copy(int(item["id"])) if item.get("pending_changes") else None
            source = working.get("snapshot") if working else post
            markdown_content = str(source.get("markdown_content") or "")
            if markdown_content and not _markdown_has_section_heading(markdown_content):
                without_sections += 1
            for alt, url in _markdown_images(markdown_content):
                if not alt or alt.lower() in {"image", "img", "\u56fe\u7247"}:
                    empty_alt += 1
                clean_url = unquote(url.split("?", 1)[0].split("#", 1)[0])
                if clean_url.startswith("/uploads/media/"):
                    candidate = UPLOADS_DIR / "media" / Path(clean_url).name
                    if not candidate.is_file():
                        missing_images += 1
        media_assets = self.list_media_assets()
        return {
            "missing_cover": sum(1 for item in active if not item.get("cover_image")),
            "missing_taxonomy": sum(1 for item in active if not item.get("category") or not item.get("tags")),
            "missing_sections": without_sections,
            "missing_images": missing_images,
            "empty_image_alt": empty_alt,
            "unreferenced_media": sum(1 for item in media_assets if not item.get("reference_count")),
        }

    def stats(self) -> dict[str, Any]:
        with self.connect() as connection:
            post_count = connection.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            draft_count = connection.execute("SELECT COUNT(*) FROM posts WHERE status = 'draft'").fetchone()[0]
            published_count = connection.execute("SELECT COUNT(*) FROM posts WHERE status = 'published'").fetchone()[0]
            trashed_count = connection.execute("SELECT COUNT(*) FROM posts WHERE status = 'trashed'").fetchone()[0]
            pending_changes_count = connection.execute("SELECT COUNT(*) FROM post_working_copies").fetchone()[0]
        return {
            "db_path": str(self.db_path),
            "post_count": post_count,
            "published_count": published_count,
            "draft_count": draft_count,
            "trashed_count": trashed_count,
            "pending_changes_count": pending_changes_count,
            "upload_dir": str(UPLOADS_DIR),
        }




