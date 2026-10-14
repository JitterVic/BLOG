"""栏目（大类）词表：前台唯一允许的粗粒度分类。

设计取舍：前台只按「栏目」这一个维度筛选，理由是可枚举的少数几个选择才可能长期整洁；
细粒度信息交给 `tags`（可展示）与 `keywords`（只检索、不展示）。因此这里给出一份
预设词表，管理后台用它做输入建议，发布校验用它做提示——栏目录入得越随意，
前台筛选条就越会退化成第二个标签云。
"""

from __future__ import annotations

CATEGORY_PRESETS = (
    "算法",
    "工程",
    "教学",
    "项目",
    "随想",
    "读书",
)

# 栏目总数超过这个量时会提示收敛：前台筛选条按「一行放得下」设计。
CATEGORY_SOFT_LIMIT = 8


def is_preset_category(value: str) -> bool:
    return str(value or "").strip() in CATEGORY_PRESETS


def merge_categories(*groups) -> list[str]:
    """预设词表在前、实际使用过的栏目在后，去重并保持稳定顺序。"""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group or ():
            value = str(item or "").strip()
            key = value.lower()
            if value and key not in seen:
                seen.add(key)
                merged.append(value)
    return merged
