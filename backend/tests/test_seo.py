"""seo 模块级测试：时间格式化、meta 注入、feed/sitemap 构建。"""

import pytest

from blog.seo import atom_datetime, build_atom_feed, build_sitemap, inject_post_meta


def test_atom_datetime_normalizes_formats():
    assert atom_datetime("2099-05-01") == "2099-05-01T00:00:00Z"
    assert atom_datetime("2099-05-01T08:00:00") == "2099-05-01T08:00:00Z"
    assert atom_datetime("2099-05-01T08:00:00Z") == "2099-05-01T08:00:00Z"
    assert atom_datetime(None).endswith("Z")


def test_inject_post_meta_escapes_and_inserts_og_tags():
    shell = "<html><head><title>站名</title></head><body></body></html>"
    post = {
        "slug": "demo",
        "title": '危险 <script> & "引号"',
        "excerpt": "摘要 & <b>富文本</b>",
        "cover_image": "/uploads/media/cover.png",
    }
    result = inject_post_meta(shell, post, lambda path: "https://example.com" + path)
    assert "<script>" not in result.split("</head>")[0]
    assert 'property="og:type" content="article"' in result
    assert "https://example.com/posts/demo" in result
    assert "https://example.com/uploads/media/cover.png" in result
    assert 'rel="canonical"' in result


def test_inject_post_meta_replaces_existing_description():
    shell = '<html><head><title>t</title><meta name="description" content="old" /></head></html>'
    post = {"slug": "demo", "title": "标题", "excerpt": "new-desc", "cover_image": ""}
    result = inject_post_meta(shell, post, lambda path: "https://example.com" + path)
    assert 'content="new-desc"' in result
    assert 'content="old"' not in result


class FakeStore:
    def __init__(self, posts):
        self._posts = posts

    def list_posts(self, **kwargs):
        return self._posts


@pytest.fixture()
def fake_store():
    return FakeStore(
        [
            {
                "slug": "hello",
                "title": '你好 <世界>',
                "excerpt": "摘要 & 摘要",
                "published_at": "2099-01-02",
                "updated_at": "2099-01-03",
            }
        ]
    )


def test_build_atom_feed_escapes_entry_fields(fake_store, monkeypatch):
    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", "https://example.com")
    body = build_atom_feed(fake_store)
    assert "<title>至知</title>" in body
    assert "你好 &lt;世界&gt;" in body
    assert "https://example.com/posts/hello" in body
    assert "<updated>2099-01-03T00:00:00Z</updated>" in body


def test_build_sitemap_lists_static_pages_and_posts(fake_store, monkeypatch):
    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", "https://example.com")
    body = build_sitemap(fake_store)
    assert "<loc>https://example.com/</loc>" in body
    assert "<loc>https://example.com/posts/hello</loc>" in body
    assert "<lastmod>2099-01-03</lastmod>" in body
