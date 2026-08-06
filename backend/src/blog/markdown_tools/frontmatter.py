"""Markdown 文件的 front-matter 解析与编码探测。"""

from __future__ import annotations

from typing import Any

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


def decode_markdown_file(raw_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")
