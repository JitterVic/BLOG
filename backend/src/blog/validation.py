"""表单字段长度校验：管理后台与 API 共用的文本字段约束。"""

from __future__ import annotations

MAX_FIELD_LENGTHS = {
    "name": 120, "headline": 240,
    "summary": 1000, "email": 320,
    "github_label": 240, "github_url": 2048, "about_intro": 12_000,
    "title": 240, "slug": 240,
    "excerpt": 1200, "published_at": 32, "read_time": 32,
    "category": 120, "tags": 1200, "keywords": 1200, "hero_quote": 1000,
    "cover_image": 2048, "markdown_content": 500_000,
}


def validate_text_length(field: str, value: str, *, max_length: int | None = None) -> str:
    normalized = str(value or "").strip()
    limit = max_length or MAX_FIELD_LENGTHS.get(field)
    if limit and len(normalized) > limit:
        raise ValueError(f"{field}内容过长，请控制在 {limit} 个字符以内。")
    return normalized
