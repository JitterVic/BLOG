"""serializers 模块级测试：载荷裁剪与表单转换。"""

from blog.serializers import (
    build_edit_post,
    build_post_detail_payload,
    build_profile_form,
    form_value,
    summarize_adjacent_post,
    summarize_post,
    summarize_related_post,
)


def make_post(**overrides):
    post = {
        "id": 1,
        "slug": "demo",
        "title": "演示",
        "excerpt": "摘要",
        "published_at": "2099-01-01",
        "read_time": "3 min",
        "category": "技术",
        "tags": ["python"],
        "hero_quote": "引言",
        "cover_image": "/uploads/media/a.png",
        "click_count": 7,
        "markdown_content": "正文",
        "html_content": "<p>正文</p>",
        "sections": [],
        "status": "published",
    }
    post.update(overrides)
    return post


def test_summarize_post_excludes_body_and_internal_fields():
    payload = summarize_post(make_post())
    assert set(payload) == {
        "slug", "title", "excerpt", "published_at", "read_time",
        "category", "tags", "cover_image", "click_count",
    }
    assert payload["click_count"] == 7


def test_summarize_post_defaults_missing_optional_fields():
    payload = summarize_post(make_post(cover_image=None, click_count=None))
    assert payload["cover_image"] == ""
    assert payload["click_count"] == 0


def test_related_and_adjacent_summaries_are_minimal():
    assert set(summarize_related_post(make_post())) == {"slug", "title", "excerpt", "category"}
    assert set(summarize_adjacent_post(make_post())) == {"slug", "title"}


def test_detail_payload_includes_navigation_blocks():
    payload = build_post_detail_payload(
        make_post(),
        related_posts=[{"slug": "r"}],
        previous_post={"slug": "p"},
        next_post=None,
    )
    assert payload["html_content"] == "<p>正文</p>"
    assert payload["related_posts"] == [{"slug": "r"}]
    assert payload["previous_post"] == {"slug": "p"}
    assert payload["next_post"] is None


def test_build_edit_post_empty_template():
    empty = build_edit_post(None)
    assert empty["status"] == "draft"
    assert empty["tags_text"] == ""


def test_build_edit_post_joins_tags_and_clears_anonymous_draft_slug():
    post = build_edit_post(make_post(tags=["a", "b"]))
    assert post["tags_text"] == "a, b"
    assert post["live_title"] == "演示"

    untitled = build_edit_post(make_post(title="", slug="draft-abc123"))
    assert untitled["slug"] == ""


def test_form_value_is_tolerant():
    assert form_value({"a": " x "}, "a") == "x"
    assert form_value({"a": None}, "a", "d") == "d"
    assert form_value(None, "a", "d") == "d"
    assert form_value(["not", "a", "mapping"], "a", "d") == "d"


def test_build_profile_form_flattens_github_and_intro():
    profile = {
        "name": "作者",
        "social_links": [
            {"label": "GitHub 仓库", "value": "blog", "url": "https://example.com/repo"},
        ],
        "about_intro": ["第一行", "第二行"],
    }
    form = build_profile_form(profile)
    assert form["github_label"] == "blog"
    assert form["github_url"] == "https://example.com/repo"
    assert form["about_intro_text"] == "第一行\n第二行"
