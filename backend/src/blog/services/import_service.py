"""导入服务：解析外部 Markdown 文件为写作表单载荷。"""

from __future__ import annotations

from typing import Any

from .. import uploads
from ..markdown_tools import (
    build_excerpt,
    decode_markdown_file,
    estimate_read_time,
    parse_markdown_front_matter,
    render_markdown,
    slugify,
    strip_leading_title_heading,
)


class ImportService:
    def import_markdown(self, file_storage) -> dict[str, Any]:
        uploads.validate_extension(file_storage.filename or "", uploads.ALLOWED_MARKDOWN_EXTENSIONS, "Markdown 文件")
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
        keywords = metadata.get("keywords") if isinstance(metadata.get("keywords"), list) else []
        excerpt = str(metadata.get("excerpt") or "").strip() or build_excerpt(markdown_content)
        requested_slug = str(metadata.get("slug") or "").strip()
        return {
            "title": guessed_title,
            "slug": requested_slug or (slugify(guessed_title) if guessed_title else ""),
            "tags": tags,
            "tags_text": ", ".join(tags),
            "keywords": keywords,
            "keywords_text": ", ".join(keywords),
            "category": str(metadata.get("category") or "").strip(),
            "published_at": str(metadata.get("date") or "").strip(),
            "cover_image": str(metadata.get("cover") or "").strip(),
            "excerpt": excerpt,
            "hero_quote": str(metadata.get("hero_quote") or "").strip(),
            "markdown_content": markdown_content,
            "html_content": render_markdown(markdown_content),
            "read_time": estimate_read_time(markdown_content),
        }
