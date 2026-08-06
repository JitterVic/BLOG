"""markdown_tools 模块级测试：分析、front-matter、渲染消毒。"""

from blog.markdown_tools import (
    build_excerpt,
    decode_markdown_file,
    estimate_read_time,
    markdown_has_heading_space_issue,
    markdown_has_section_heading,
    markdown_has_unclosed_fence,
    markdown_images,
    parse_markdown_front_matter,
    render_markdown,
    slugify,
    strip_leading_title_heading,
)


def test_slugify_keeps_chinese_and_dedupes_separators():
    assert slugify("Hello 世界 / Post") == "hello-世界-post"
    assert slugify("---").startswith("post-")


def test_estimate_read_time_counts_chinese_and_english():
    assert estimate_read_time("") == "1 min"
    long_text = "word " * 560
    assert estimate_read_time(long_text) == "2 min"


def test_build_excerpt_strips_markdown_syntax():
    excerpt = build_excerpt("# 标题\n\n![图](x.png)正文 [链接](/a) `code`")
    assert "![" not in excerpt
    assert "链接" in excerpt
    assert "code" in excerpt


def test_markdown_checks():
    assert markdown_has_unclosed_fence("```\ncode") is True
    assert markdown_has_unclosed_fence("```\ncode\n```") is False
    assert markdown_has_heading_space_issue("#缺少空格") is True
    assert markdown_has_heading_space_issue("# 正常") is False
    assert markdown_has_section_heading("## 章节") is True
    assert markdown_has_section_heading("只有正文") is False


def test_markdown_images_extracts_alt_and_url():
    images = markdown_images('![封面](/uploads/media/a.png "标题") 和 ![](/b.jpg)')
    assert images == [("封面", "/uploads/media/a.png"), ("", "/b.jpg")]


def test_strip_leading_title_heading_only_when_duplicated():
    assert strip_leading_title_heading("# 同名\n\n正文", "同名") == "正文\n"
    assert strip_leading_title_heading("# 其他\n\n正文", "同名").startswith("# 其他")


def test_parse_front_matter_supports_known_keys_only():
    content = "---\ntitle: 文章\ntags: [a, b]\nunknown: x\n---\n\n正文"
    metadata, body = parse_markdown_front_matter(content)
    assert metadata["title"] == "文章"
    assert metadata["tags"] == ["a", "b"]
    assert "unknown" not in metadata
    assert body == "正文"


def test_parse_front_matter_returns_original_without_delimiter():
    metadata, body = parse_markdown_front_matter("正文而已")
    assert metadata == {}
    assert body == "正文而已"


def test_decode_markdown_file_tries_multiple_encodings():
    assert decode_markdown_file("中文".encode("utf-8")) == "中文"
    assert decode_markdown_file("中文".encode("gbk")) == "中文"


def test_render_markdown_drops_dangerous_html():
    html = render_markdown('<script>alert(1)</script> 文本 <a href="javascript:void(0)">链接</a>')
    assert "<script>" not in html
    assert "alert(1)" not in html
    assert 'href="javascript' not in html


def test_render_markdown_keeps_safe_elements():
    html = render_markdown("## 标题\n\n[站内](/posts) ![图](/uploads/media/a.png)")
    assert "<h2>" in html
    assert 'href="/posts"' in html
    assert "/uploads/media/a.png" in html


def test_render_markdown_normalizes_nbsp():
    html = render_markdown("```\ncode\xa0line\n```")
    assert "\xa0" not in html
