"""Markdown 文本分析：slug、阅读时长、摘要生成与正文质量检查（纯函数，无 IO）。"""

from __future__ import annotations

import math
import re
from datetime import datetime

MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[\"\'][^)]*[\"\'])?\)")
MEDIA_URL_PATTERN = re.compile(r"/uploads/media/([^\s)\]\"\'<>?#]+)", re.IGNORECASE)


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


def build_excerpt(markdown_content: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", markdown_content)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^```.*?^```", " ", text, flags=re.S | re.M)
    text = re.sub(r"[#>*`\-|]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:120] + ("..." if len(text) > 120 else "")


def markdown_has_unclosed_fence(markdown_content: str) -> bool:
    fence_count = sum(1 for line in str(markdown_content or "").splitlines() if re.match(r"^\s*```", line))
    return fence_count % 2 == 1


def markdown_has_heading_space_issue(markdown_content: str) -> bool:
    return bool(re.search(r"(?:^|\n)#{1,6}[^#\s\n]", str(markdown_content or "")))


def markdown_has_section_heading(markdown_content: str) -> bool:
    return bool(re.search(r"(?:^|\n)##\s+\S", str(markdown_content or "")))


def markdown_images(markdown_content: str) -> list[tuple[str, str]]:
    return [
        (match.group(1).strip(), match.group(2).strip())
        for match in MARKDOWN_IMAGE_PATTERN.finditer(str(markdown_content or ""))
    ]


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
    remaining = lines[:index] + lines[index + 1:]
    while remaining and not remaining[0].strip():
        remaining = remaining[1:]
    joined = "\n".join(remaining).strip()
    return (joined + "\n") if joined else ""
