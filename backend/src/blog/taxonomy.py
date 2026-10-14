"""栏目（大类）词表：前台唯一允许的粗粒度分类。

设计取舍：前台只按「栏目」这一个维度筛选，理由是可枚举的少数几个选择才可能长期整洁；
细粒度信息交给 `tags`（可展示、自由词表）与 `keywords`（只检索、不展示）。因此这里
给出一份**固定**词表：管理后台的栏目控件是下拉选择，发布预检也会拒绝词表以外的值——
栏目录入得越随意，前台筛选条就越会退化成第二个标签云。
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


def is_preset_category(value: str) -> bool:
    return str(value or "").strip() in CATEGORY_PRESETS
