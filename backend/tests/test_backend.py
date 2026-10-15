import io
import importlib
import re
import time
from pathlib import Path

import pytest
from PIL import Image

from blog.serializers import build_edit_post, build_post_detail_payload, summarize_post
from blog.store import PostVersionConflict
from blog.taxonomy import CATEGORY_PRESETS


@pytest.fixture()
def app_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOG_DEBUG", "true")
    monkeypatch.setenv("BLOG_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/admin")
    monkeypatch.setenv("BLOG_REQUIRE_PUBLIC_BASE_URL", "false")
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "false")
    monkeypatch.delenv("BLOG_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("BLOG_DATABASE_PATH", str(tmp_path / "blog.db"))
    monkeypatch.setenv("BLOG_LOGIN_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("BLOG_LOGIN_RATE_WINDOW_SECONDS", "60")
    monkeypatch.setenv("BLOG_MAX_IMAGE_BYTES", str(512 * 1024))

    app_module = importlib.import_module("blog.app")
    store_module = importlib.import_module("blog.store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
    uploads_module = importlib.import_module("blog.uploads")
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(app_module, "UPLOADS_DIR", uploads_dir)

    application = app_module.create_app()
    application.config.update(TESTING=True)
    return application, store_module.BlogStore(tmp_path / "blog.db")


@pytest.fixture()
def client(app_bundle):
    application, _store = app_bundle
    return application.test_client()


def csrf_token(client):
    client.get("/admin/login")
    with client.session_transaction() as session:
        return session["_admin_csrf_token"]


def login(client):
    token = csrf_token(client)
    response = client.post("/admin/login", data={"password": "test-password", "csrf_token": token})
    assert response.status_code == 302
    with client.session_transaction() as session:
        return session["_admin_csrf_token"]


def image_bytes(format_name="PNG"):
    output = io.BytesIO()
    Image.new("RGB", (16, 16), "#b45309").save(output, format=format_name)
    output.seek(0)
    return output


def test_health_does_not_expose_database_path(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_public_api_excludes_drafts(app_bundle, client):
    _application, store = app_bundle
    draft_id = store.save_post(
        {"title": "Hidden Draft", "slug": "hidden-draft", "markdown_content": "secret"},
        action="draft",
    )
    assert store.get_post_by_id(draft_id)["status"] == "draft"
    response = client.get("/api/posts?q=Hidden Draft")
    assert response.status_code == 200
    assert response.get_json()["items"] == []
    assert client.get("/api/posts/hidden-draft").status_code == 404


def test_markdown_sanitizes_dangerous_links_and_tags(app_bundle):
    _application, store = app_bundle
    html = importlib.import_module("blog.store").render_markdown(
        '[bad](javascript:alert(1)) <script>alert(1)</script>\n\n![x](javascript:alert(1))'
    )
    assert "javascript:" not in html.lower()
    assert "<script" not in html.lower()


def test_admin_api_requires_auth_and_csrf(client):
    response = client.post("/admin/api/preview-markdown", json={"markdown_content": "# hi"})
    assert response.status_code == 401
    assert response.get_json()["code"] == "auth_required"

    token = login(client)
    response = client.post("/admin/api/preview-markdown", json={"markdown_content": "# hi"})
    assert response.status_code == 400
    assert response.get_json()["code"] == "csrf_failed"

    response = client.post(
        "/admin/api/preview-markdown",
        json={"markdown_content": "# hi"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    # 正文标题降一级：文章标题由页面 h1 承担，正文 `#` 渲染为 h2。
    assert response.get_json()["html"] == "<h2>hi</h2>"


def test_logout_is_post_and_clears_session(client):
    token = login(client)
    assert client.get("/admin/logout").status_code in {404, 405}
    response = client.post("/admin/logout", data={"csrf_token": token})
    assert response.status_code == 302
    assert response.location.endswith("/admin/login")
    assert client.get("/admin").status_code == 302


def test_login_rate_limit_returns_429(client):
    token = csrf_token(client)
    for _ in range(3):
        assert client.post("/admin/login", data={"password": "wrong", "csrf_token": token}).status_code == 200
    response = client.post("/admin/login", data={"password": "wrong", "csrf_token": token})
    assert response.status_code == 429
    assert response.headers["Retry-After"]


def test_autosave_version_conflict(app_bundle, client):
    _application, store = app_bundle
    token = login(client)
    fields = {"title": "Autosaved", "slug": "autosaved", "markdown_content": "one"}
    response = client.post(
        "/admin/api/autosave",
        json={"fields": fields},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    payload = response.get_json()
    post_id = payload["id"]
    old_updated_at = payload["updated_at"]

    time.sleep(1.05)
    store.save_post(
        {"title": "Autosaved newer", "slug": "autosaved", "markdown_content": "newer"},
        post_id=post_id,
        action="draft",
    )
    response = client.post(
        "/admin/api/autosave",
        json={"post_id": post_id, "updated_at": old_updated_at, "fields": fields},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 409
    assert response.get_json()["code"] == "version_conflict"


def test_image_upload_rejects_fake_files_and_accepts_real_images(app_bundle, client):
    _application, _store = app_bundle
    token = login(client)
    fake = client.post(
        "/admin/api/upload-image",
        data={"image": (io.BytesIO(b"not-an-image"), "fake.png")},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )
    assert fake.status_code == 400
    assert fake.get_json()["code"] == "validation_error"

    valid = client.post(
        "/admin/api/upload-image",
        data={"image": (image_bytes(), "cover.png")},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )
    assert valid.status_code == 200
    assert valid.get_json()["url"].startswith("/uploads/media/")


def test_search_tags_and_pagination(app_bundle, client):
    _application, store = app_bundle
    store.save_post(
        {
            "title": "Flask Notes",
            "slug": "flask-notes",
            "markdown_content": "## Section\n\nSome body text.",
            "tags": "Flask, Vue",
        },
        action="published",
    )
    response = client.get("/api/posts?q=Flask&page=1&limit=1")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"] == 1
    assert payload["per_page"] == 1
    assert payload["total"] >= 1
    assert len(payload["items"]) == 1
    assert "Flask" in payload["items"][0]["tags"]


def test_admin_phase_two_pages_render_accessible_controls(app_bundle, client):
    _application, store = app_bundle
    store.save_post(
        {"title": "List Me", "slug": "list-me", "markdown_content": "body"},
        action="published",
    )
    login(client)
    dashboard = client.get("/admin").get_data(as_text=True)
    assert "dashboard-overview" in dashboard
    assert "dashboard-stat" in dashboard
    assert "data-confirm-form" in dashboard
    assert 'aria-live="polite"' in dashboard

    profile = client.get("/admin/profile").get_data(as_text=True)
    assert 'id="profile-form"' in profile
    assert "field-help" in profile
    assert "data-loading-form" in profile
    assert "avatar" not in profile
    assert 'name="hero_note"' not in profile
    assert 'name="update_calendar"' not in profile


def test_write_save_redirect_marks_success_for_local_draft_cleanup(client):
    token = login(client)
    response = client.post(
        "/admin/posts/save",
        data={
            "csrf_token": token,
            "title": "Submitted article",
            "slug": "submitted-article",
            "markdown_content": "# Submitted article\n\nBody",
            "action": "draft",
        },
    )
    assert response.status_code == 302
    assert "saved=1" in response.location


def test_markdown_import_endpoint_returns_editor_fields(client):
    token = login(client)
    response = client.post(
        "/admin/api/import-markdown",
        data={
            "markdown_file": (io.BytesIO(b"---\ntitle: Imported\ntags: [one, two]\n---\n\n# Imported\n\nBody"), "import.md")
        },
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["title"] == "Imported"
    assert payload["markdown_content"].lstrip().startswith("Body")
    assert not payload["markdown_content"].lstrip().startswith("# Imported")
    assert payload["tags"] == ["one", "two"]


def test_writing_editor_phase_three_contract_is_present():
    template = Path("backend/src/blog/templates/admin_write.html").read_text(encoding="utf-8")
    module_dir = Path("backend/src/blog/static/admin/js/write")
    script = "\n".join(
        item.read_text(encoding="utf-8") for item in sorted(module_dir.glob("*.js"))
    )
    assert "data-form-saved" in template
    assert "retry-autosave" in template
    for marker in (
        "AbortController",
        "serverSaveInFlight",
        "showRetryAutosave",
        "validatePostSubmission",
        "replaceUploadPlaceholder",
        "clearSavedLocalDraft",
    ):
        assert marker in script


def test_related_posts_uses_compact_query(app_bundle, client):
    _application, store = app_bundle
    unique_category = CATEGORY_PRESETS[1]
    unique_tag = "phase-five-unique-tag"
    base = {
        "title": "Primary related article",
        "slug": "primary-related",
        "category": unique_category,
        "tags": unique_tag,
        "markdown_content": "# Primary\n\nBody",
        "published_at": "2099-01-10",
    }
    store.save_post(base, action="published")
    store.save_post(
        {
            "title": "Same tags article",
            "slug": "same-tags-related",
            "category": CATEGORY_PRESETS[2],
            "tags": unique_tag,
            "markdown_content": "# Same tags\n\nBody",
            "published_at": "2099-01-09",
        },
        action="published",
    )
    store.save_post(
        {
            "title": "Same category article",
            "slug": "same-category-related",
            "category": unique_category,
            "tags": "other-tag",
            "markdown_content": "# Same category\n\nBody",
            "published_at": "2099-01-08",
        },
        action="published",
    )

    primary = store.get_post_by_slug("primary-related")
    related = store.get_related_posts(primary, limit=2)
    assert [item["slug"] for item in related] == ["same-tags-related", "same-category-related"]
    assert "markdown_content" not in related[0]
    assert "html_content" not in related[0]

    response = client.get("/api/posts/primary-related")
    assert response.status_code == 200
    payload = response.get_json()
    assert [item["slug"] for item in payload["related_posts"]] == [
        "same-tags-related",
        "same-category-related",
    ]
    for item in payload["related_posts"]:
        assert set(item.keys()) == {"slug", "title", "excerpt", "category"}


def test_view_count_increments_once_per_session(app_bundle, client):
    _application, store = app_bundle
    store.save_post(
        {
            "title": "Counted article",
            "slug": "counted-article",
            "markdown_content": "# Counted\n\nBody",
            "published_at": "2026-02-01",
        },
        action="published",
    )
    first = client.get("/api/posts/counted-article")
    assert first.status_code == 200
    assert store.get_post_by_slug("counted-article")["click_count"] == 1

    second = client.get("/api/posts/counted-article")
    assert second.status_code == 200
    assert store.get_post_by_slug("counted-article")["click_count"] == 1

    other = client.application.test_client()
    third = other.get("/api/posts/counted-article")
    assert third.status_code == 200
    assert store.get_post_by_slug("counted-article")["click_count"] == 2


def test_field_length_limits_reject_oversized_title(app_bundle):
    _application, store = app_bundle
    try:
        store.save_post(
            {
                "title": "x" * 300,
                "slug": "too-long-title",
                "markdown_content": "body",
            },
            action="draft",
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "标题" in str(exc) or "title" in str(exc).lower() or "长度" in str(exc)


def test_sqlite_connection_enables_wal_and_foreign_keys(app_bundle):
    _application, store = app_bundle
    with store.connect() as connection:
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()[0]
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    assert int(foreign_keys) == 1
    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) >= 5000


def test_production_rejects_default_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOG_DEBUG", "false")
    monkeypatch.setenv("BLOG_DATABASE_PATH", str(tmp_path / "blog.db"))

    app_module = importlib.import_module("blog.app")

    monkeypatch.setenv("BLOG_SECRET_KEY", "dev-secret-key-change-me")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "strong-enough-password")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/launch-admin")
    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "true")
    with pytest.raises(RuntimeError, match="BLOG_SECRET_KEY"):
        app_module.create_app()

    monkeypatch.setenv("BLOG_SECRET_KEY", "unique-test-secret-1234567890abcdef")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "admin123456")
    with pytest.raises(RuntimeError, match="BLOG_ADMIN_PASSWORD"):
        app_module.create_app()

    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "strong-enough-password")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/admin")
    with pytest.raises(RuntimeError, match="BLOG_ADMIN_PREFIX"):
        app_module.create_app()

    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/launch-admin")
    monkeypatch.delenv("BLOG_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("BLOG_COOKIE_SECURE", raising=False)
    monkeypatch.setenv("BLOG_REQUIRE_PUBLIC_BASE_URL", "true")
    with pytest.raises(RuntimeError, match="BLOG_PUBLIC_BASE_URL"):
        app_module.create_app()

    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "false")
    with pytest.raises(RuntimeError, match="BLOG_COOKIE_SECURE"):
        app_module.create_app()

    monkeypatch.setenv("BLOG_COOKIE_SECURE", "true")
    launched = app_module.create_app()
    assert launched.config["ADMIN_PREFIX"] == "/launch-admin"
    assert launched.config["BLOG_REQUIRE_PUBLIC_BASE_URL"] is True

    monkeypatch.setenv("BLOG_REQUIRE_PUBLIC_BASE_URL", "false")
    monkeypatch.delenv("BLOG_PUBLIC_BASE_URL", raising=False)
    monkeypatch.delenv("BLOG_COOKIE_SECURE", raising=False)
    relaxed = app_module.create_app()
    assert relaxed.config["BLOG_REQUIRE_PUBLIC_BASE_URL"] is False


def test_security_headers_present_on_html_and_api(client):
    html = client.get("/admin/login")
    assert html.status_code == 200
    assert html.headers.get("X-Frame-Options") == "DENY"
    assert html.headers.get("X-Content-Type-Options") == "nosniff"
    assert "strict-origin-when-cross-origin" in (html.headers.get("Referrer-Policy") or "")
    assert "default-src 'self'" in (html.headers.get("Content-Security-Policy") or "")

    api = client.get("/api/health")
    assert api.status_code == 200
    assert api.headers.get("X-Frame-Options") == "DENY"
    assert api.headers.get("X-Content-Type-Options") == "nosniff"


def test_svg_is_not_served_from_uploads(app_bundle, client):
    _application, _store = app_bundle
    uploads = Path(importlib.import_module("blog.store").UPLOADS_DIR)
    media = uploads / "media"
    media.mkdir(parents=True, exist_ok=True)
    target = media / "evil.svg"
    target.write_text("<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", encoding="utf-8")
    response = client.get("/uploads/media/evil.svg")
    assert response.status_code == 404


def test_env_int_falls_back_on_invalid_values(monkeypatch):
    env_loader = importlib.import_module("blog.env_loader")
    monkeypatch.setenv("BLOG_PORT", "not-a-number")
    with pytest.warns(RuntimeWarning):
        assert env_loader.env_int("BLOG_PORT", 5000) == 5000


def test_list_posts_omits_body_columns(app_bundle, client):
    _application, store = app_bundle
    store.save_post(
        {
            "title": "Compact list body",
            "slug": "compact-list-body",
            "markdown_content": "# Compact\n\nLong body should not appear in list query rows.",
            "published_at": "2099-03-01",
        },
        action="published",
    )
    listed = store.list_posts(published_only=True)
    match = next(item for item in listed if item["slug"] == "compact-list-body")
    assert "markdown_content" not in match
    assert "html_content" not in match
    assert match["title"] == "Compact list body"

    payload = client.get("/api/posts").get_json()
    item = next(entry for entry in payload["items"] if entry["slug"] == "compact-list-body")
    assert set(item.keys()) >= {"slug", "title", "excerpt", "cover_image", "click_count"}
    assert "html_content" not in item
    assert "markdown_content" not in item

    admin_rows = store.list_admin_posts()
    assert len(admin_rows) <= 200
    admin_match = next(item for item in admin_rows if item["slug"] == "compact-list-body")
    assert "markdown_content" not in admin_match


def test_import_strips_duplicate_leading_h1(app_bundle, client):
    _application, store = app_bundle
    class FakeFile:
        filename = "dup.md"
        def read(self):
            return b"---\ntitle: Same Title\n---\n\n# Same Title\n\nBody text"
    payload = store.import_markdown(FakeFile())
    assert payload["title"] == "Same Title"
    assert payload["markdown_content"].lstrip().startswith("Body text")
    assert not payload["markdown_content"].lstrip().startswith("# Same Title")


def test_heic_is_rejected_by_upload_whitelist(app_bundle, client):
    _application, _store = app_bundle
    token = login(client)
    response = client.post(
        "/admin/api/upload-image",
        data={"image": (io.BytesIO(b"not-real"), "photo.heic")},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "validation_error"


def test_admin_loading_form_respects_prevented_submit():
    script = Path("backend/src/blog/static/admin/admin.js").read_text(encoding="utf-8")
    assert "event.defaultPrevented" in script
    assert 'form.dataset.submitting = "true"' in script
    # loading lock must not run when validation already cancelled submit
    idx = script.index("event.defaultPrevented")
    lock = script.index("form.dataset.submitting")
    assert idx < lock


def test_write_page_exposes_publish_status_chrome(client):
    login(client)
    page = client.get("/admin/write").get_data(as_text=True)
    assert "write-status-badge" in page
    assert "autosave-status" in page
    assert "write-status-bar" in page
    assert "published-autosave-tip" not in page


def test_css_contains_no_toc_rule():
    admin_css = Path("backend/src/blog/static/admin/css/write.css").read_text(encoding="utf-8")
    front_css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    assert "write-status-badge" in admin_css
    assert ("post-reading-layout--no-toc" in front_css) or ("--no-toc" in front_css) or ("post-reading-layout--no-toc" in admin_css)


def test_toc_scroll_offset_variables_are_in_scope():
    """标题落点用的自定义属性必须声明在目录与正文的共同祖先上。

    自定义属性不向上查找。若把 `--toc-strip-height` 声明在 `.article-toc` 上，
    兄弟节点里的标题读不到它，`calc()` 会在计算值阶段把整条声明判为无效并退化成
    `scroll-margin-top: 0`——目录点击后标题正好顶到目录条下面，且没有任何报错。
    """
    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    assert "scroll-margin-top: calc(var(--toc-sticky-top) + var(--toc-strip-height)" in css

    # 窄屏分支：两个变量都要落在 .post-reading-layout 上（目录与正文的共同祖先）
    narrow = css.split("@media (max-width: 1280px)", 1)
    assert len(narrow) == 2, "找不到窄屏媒体查询"
    narrow_body = narrow[1]
    layout_blocks = re.findall(r"\.post-reading-layout\s*\{([^}]*)\}", narrow_body, re.S)
    assert layout_blocks, "窄屏分支里找不到 .post-reading-layout 规则块"
    declared = "\n".join(layout_blocks)
    assert "--toc-sticky-top" in declared
    assert "--toc-strip-height" in declared

    # 目录自身只能「使用」这两个变量，不能「声明」它们（声明会让标题读不到，
    # 这正是修掉的那个 bug）。用 `变量名:` 判断声明而非引用。
    for toc_body in re.findall(r"\.article-toc\s*\{([^}]*)\}", css, re.S):
        assert "--toc-strip-height:" not in toc_body, (
            "目录高度变量必须声明在 .post-reading-layout 上，否则正文标题读不到"
        )
        assert "--toc-sticky-top:" not in toc_body, (
            "吸附位置变量必须声明在 .post-reading-layout 上，否则正文标题读不到"
        )


def test_article_rail_width_tokens_are_in_scope():
    """左侧清单的宽度与间隙变量必须声明在 `.post-reading-layout` 上。

    与目录的吸附变量同理：面板是这份网格的并列子元素，自定义属性既不向上查找、也不
    横向传递。若把 `--post-rail-width` 声明在 `.article-rail` 上，`min()` 会在计算值
    阶段被整条判为无效并退化成 auto 宽度，清单就会压到正文轨道上，而且不报错。
    """
    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    layout_blocks = re.findall(r"\.post-reading-layout\s*\{([^}]*)\}", css, re.S)
    assert layout_blocks, "找不到 .post-reading-layout 规则块"
    declared = "\n".join(layout_blocks)
    assert "--post-rail-width" in declared
    assert "--post-rail-gap" in declared

    rail_blocks = re.findall(r"\.article-rail\s*\{([^}]*)\}", css, re.S)
    assert rail_blocks, "找不到 .article-rail 规则块"
    for body in rail_blocks:
        assert "--post-rail-width:" not in body, (
            "清单宽度变量必须声明在 .post-reading-layout 上，否则 min() 夹不住宽度"
        )
        assert "--post-rail-gap:" not in body, (
            "清单间隙变量必须声明在 .post-reading-layout 上，否则 min() 夹不住宽度"
        )


def test_side_panels_cannot_reach_the_reading_column():
    """左右面板都不能挤动正文轨道，也不能压到版面框上。

    正文能恒定居中、宽度不变，靠的是「三条轨道宽度固定 + 面板只决定自己那一格里的
    位置」：面板宽度用 min() 夹在自己那格的轨道宽以内，左右各自贴向本侧（left: 0 /
    right: 0）。面板是绝对定位的网格子元素，包含块就是它自己那一格，所以这里的
    百分比仍是轨道宽度——一旦有轨道改成 auto，或把面板宽度改成 auto 内容撑开，
    面板就会压到正文轨道上。

    但「不挤正文」不等于「好看」：正文列只有 760px，1fr 轨道在窄一点的视口上比
    面板宽不了多少，于是面板会越过版面框的框线（实测 1440 下框左边缘在 x=125，
    而清单宽 312）。所以宽度还必须夹上第三项——版面框外侧的留白。
    """
    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    layout_blocks = re.findall(r"\.post-reading-layout\s*\{([^}]*)\}", css, re.S)
    columns = "\n".join(
        declaration
        for body in layout_blocks
        for declaration in re.findall(r"grid-template-columns\s*:([^;]*);", body)
    )
    assert columns, "找不到 .post-reading-layout 的轨道定义"
    assert "auto" not in columns, "轨道不能由内容撑开，否则面板会挤动正文"
    assert "var(--post-article-width)" in columns

    rail = "\n".join(re.findall(r"\.article-rail\s*\{([^}]*)\}", css, re.S))
    for term in (
        "var(--post-rail-width)",
        "calc(100% - var(--post-rail-gap))",
        "var(--post-outer-margin",
    ):
        assert term in rail, f"清单宽度缺少夹取项 {term}"
    assert "left: 0" in rail
    assert "var(--post-rail-margin)" in rail, "清单的边缘余量必须与宽度上限同源"

    toc_blocks = re.findall(r"\.article-toc\s*\{([^}]*)\}", css, re.S)
    assert toc_blocks
    toc = "\n".join(toc_blocks)
    for term in (
        "var(--post-toc-width)",
        "calc(100% - var(--post-toc-gap))",
        "var(--post-outer-margin",
    ):
        assert term in toc, f"目录宽度缺少夹取项 {term}"
    assert "right: 0" in toc, "右侧目录必须贴本格右边缘"
    assert "var(--post-toc-margin)" in toc, "目录的边缘余量必须与宽度上限同源"


def test_reading_frame_narrows_to_make_room_for_the_side_panels():
    """阅读页的版面框必须随视口收窄，把两侧栏位让出来。

    1888px 以内宽度的视口放不下「1180px 的框 + 312px 清单 + 240px 目录」，
    框不收窄，面板只会越过框线。框宽与外侧留白必须来自同一个变量：
    --post-outer-margin 既是面板宽度上限的减项，也是面板与框线之间距离的来源，
    两边各算一遍迟早会漂移。
    """
    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")

    root = re.search(r"\.print-post-view\s*\{([^}]*)\}", css, re.S)
    assert root is not None, "找不到 .print-post-view 的变量声明块"
    assert "--post-frame-width" in root.group(1), "框宽必须声明在框与面板的共同祖先上"
    assert "--post-outer-margin" in root.group(1), "外侧留白必须由框宽推导"
    assert "var(--post-frame-width)" in root.group(1)

    widen = re.search(r"@media\s*\(min-width:\s*1281px\)\s*\{([^}]*)\}", css, re.S)
    assert widen is not None
    assert ".print-post-view .print-page" in widen.group(1)
    assert ".print-post-view .print-related-section" in widen.group(1), (
        "相关阅读区与正文框必须同宽，否则两个框线会错开"
    )
    assert widen.group(1).count("width: var(--post-frame-width)") == 1

    # 收窄档位必须晚于 layout.css 的原框宽规则才生效：post.css 是后加载的那一层。
    entry = Path("frontend/src/styles/editorial.css").read_text(encoding="utf-8")
    assert entry.index('"./layout.css"') < entry.index('"./post.css"'), (
        "post.css 必须排在 layout.css 之后，否则框宽覆盖不生效"
    )

    # 面板的宽度上限必须真的用上外侧留白，否则收窄框宽只是白收。
    for panel, margin_token in (
        ("article-rail", "--post-rail-margin"),
        ("article-toc", "--post-toc-margin"),
    ):
        body = re.findall(r"\." + panel + r"\s*\{([^}]*)\}", css, re.S)[0]
        width = re.search(r"width:\s*min\((.*?)\);", body, re.S)
        assert width is not None, f".{panel} 必须用 min() 夹取宽度"
        terms = width.group(1)
        assert "var(--post-outer-margin" in terms
        assert margin_token in terms
        assert "var(--post-panel-breath)" in terms, "面板与框线之间要留呼吸带"


def test_side_panels_are_pinned_without_touching_the_scroll_path():
    """吸附态必须是 fixed，且滚动过程中一行脚本都不跑。

    这里挡的是两次真实翻车：
    · 交给 position: sticky —— 它只允许面板待在那条网格区域之内，而区域高度由正文
      决定（清单不参与行高计算，目录又比正文矮）。短文下区域很快就滚过去，sticky 会
      把面板夹着一起上滑：实测 700px 高窗口 + 217px 短文，面板顶部从 109 滑到 -193，
      头部那枚收起/展开按钮先钻到固定顶栏底下、再滑出屏幕——表现就是「收起来了就打
      不开」。
    · 每帧在绝对定位的面板上手写 top —— 浏览器先把面板当普通内容滚上去，主线程之后
      才派发 scroll 事件、脚本再把 top 补回来，这一来一回必然差一帧。实测按 55px/帧
      滚动时面板顶部稳定停在 53px，而吸附线在 108.8px，偏差正好等于一帧的滚动量且
      不收敛，看上去就是面板一直在抖。fixed 元素不参与滚动，位置恒定，脚本只在跨过
      吸附线那一刻切一次类名，因此 --panel-shift 这个「每帧写一次 top」的通道必须
      彻底不存在。

    同时锁住 pointer-events：外层盒子高 0、宽度仍占着左栏，必须设 none 才不会挡住
    正文列的命中测试，而它是继承属性，面板必须显式写回 auto，否则按钮看得见却点不动。
    """
    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    for panel in ("article-rail", "article-toc"):
        blocks = re.findall(r"\." + panel + r"\s*\{([^}]*)\}", css, re.S)
        assert blocks, f"找不到 .{panel} 基准规则"
        # 只检查基准档：≤1280px 那条横向目录条本来就该留在文档流里用 sticky 吸顶
        base = re.sub(r"/\*.*?\*/", "", blocks[0], flags=re.S)
        assert "position: absolute" in base, f".{panel} 吸附前应当绝对定位"
        assert "position: sticky" not in base, f".{panel} 不能再用 sticky 吸附"
        assert "top: 0" in base, f".{panel} 吸附前应贴区域顶端，不该由脚本给坐标"

    pin_rule = re.search(
        r"\.article-rail\.is-pinned,\s*\r?\n\s*\.article-toc\.is-pinned\s*\{([^}]*)\}",
        css,
        re.S,
    )
    assert pin_rule is not None, "找不到 .is-pinned 吸附规则"
    assert "position: fixed" in pin_rule.group(1), "吸附态必须 fixed，否则会落后滚动一帧"
    assert "top: var(--panel-pin" in pin_rule.group(1), "吸附线由 --panel-pin 提供"

    # 必须限定在桌面档位里：.article-toc.is-pinned 的权重高于窄屏那条 .article-toc，
    # 跑到档位外面就会把 ≤1280px 的横向目录条也变成固定定位。
    enclosing = css[: pin_rule.start()]
    assert enclosing.rindex("@media (min-width: 1281px)") > enclosing.rfind("@media (max-width: 1280px)"), (
        ".is-pinned 必须写在 ≥1281px 档位内"
    )
    narrow = css[css.index("@media (max-width: 1280px)"):]
    assert "position: sticky" in narrow, "窄屏横向目录条仍要留在文档流里 sticky 吸顶"

    # 每帧写 top 的通道必须不存在：CSS 侧不能有 --panel-shift，脚本侧也不能写它。
    assert "--panel-shift" not in css, "不能再让脚本每帧写 top，吸附态交给 fixed"
    pin = Path("frontend/src/composables/usePanelPin.js").read_text(encoding="utf-8")
    assert "--panel-shift" not in pin
    assert '"--panel-pin"' in pin, "吸附线 px 值需要由脚本写入，与 pinRem 同源"
    assert "getBoundingClientRect" in pin and "scroll" in pin and "resize" in pin
    assert "MIN_USEFUL_PX" in pin, "区域走完时要停用面板，避免留下不可点的碎片"
    assert "panelNeedsMoreRoom" in pin, "碎片判定要看内容能否完整放下，而不是只看一个固定高度"
    # 只在数值变化时写样式，稳定态的滚动不该产生任何样式改写。
    assert "lastAvail" in pin and "if (avail !== lastAvail)" in pin

    assert "var(--panel-avail" in css, "面板可用高度需要由脚本给出"

    rail = "\n".join(re.findall(r"\.article-rail\s*\{([^}]*)\}", css, re.S))
    assert "pointer-events: none" in rail, "零高的外层盒子不该拦住正文列的点击"

    shared = re.search(r"\.article-rail__body,\s*\r?\n\s*\.article-rail__spine\s*\{([^}]*)\}", css, re.S)
    assert shared is not None
    assert "pointer-events: auto" in shared.group(1), "面板必须显式写回可点击"


def test_article_rail_is_not_laid_out_below_its_breakpoint():
    """清单在轨道不够宽时必须彻底不布局，而不是靠 JS 挡住。

    ≤1280px 的区域模板是单列 `"toc"` / `"article"`，里面没有 rail 那一格；一个仍然
    可见的面板会被自动放进隐式行，直接冒在正文上方。因此基准规则必须是
    `display: none`，由 min-width 档位打开——JS 的 matchMedia 只管发不发请求。
    """
    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    base = re.search(r"\.article-rail\s*\{([^}]*)\}", css, re.S)
    assert base is not None, "找不到 .article-rail 基准规则"
    assert "display: none" in base.group(1), "基准档必须不布局，否则窄屏会出现隐式行"

    widen = re.search(r"@media\s*\(min-width:\s*1440px\)\s*\{([^}]*)\}", css, re.S)
    assert widen is not None, "找不到清单的 min-width 档位"
    assert "display: block" in widen.group(1)

    assert base.start() < widen.start(), "基准档必须先于放宽档位"
    assert base.start() < css.index("@media (max-width: 1280px)"), (
        "基准的 display:none 必须排在窄屏单列档位之前"
    )


def test_panel_chevrons_point_outward_when_collapsing():
    """收起箭头朝外、展开箭头朝内，四条控制件都不能漏。

    四个控制件的模板路径并不统一：左栏两处与目录书脊用的是朝左的 `M15 5l-7 7 7 7`，
    目录的收起按钮用的是朝右的 `M9 5l7 7-7 7`。要满足「左栏收起朝左、左栏展开朝右、
    目录收起朝右、目录展开朝左」，只有左栏书脊需要翻转；此前错给目录的两处各加了一次
    180°，结果目录的收起键朝左（用户看到的就是这个）。与其逐个核对路径方向，不如把
    「整份 post.css 里只允许一处 rotate(180deg)，且必须落在左栏书脊上」钉死。
    """
    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    hits = re.findall(r"([^{}]+)\{([^{}]*rotate\(180deg\)[^{}]*)\}", css, re.S)
    allowed = {
        # 左栏书脊：面板从左侧拉出，展开时的箭头要指回正文
        ".article-rail__spine svg",
        # 范围切换器的折角：菜单展开时朝上
        '.article-rail__scope[aria-expanded="true"] .article-rail__scope-caret',
    }
    found = {hit[0].strip() for hit in hits}
    assert found <= allowed, f"出现了计划外的箭头翻转：{sorted(found - allowed)}"
    assert ".article-rail__spine svg" in found, "左栏书脊的箭头必须翻转，否则指向反了"
    assert ".article-toc__toggle svg" not in found and ".article-toc__spine svg" not in found, (
        "目录的两处箭头用另一条朝右的路径，本来就对，翻转会让它指反"
    )


def test_router_view_survives_query_only_navigation():
    """路由视图的 key 只能取 path，不能取 fullPath。

    取 fullPath 时任何只改查询串的导航都会换 key：`加载更多` 把 page 写回 URL 的那一刻
    整页重建，先闪一次骨架屏（看起来就是「刷新了页面」），再由 onMounted 从头拉一遍
    列表，第二页的内容才补上；从文章页点「完整目录」跳 /posts?cat=… 同理，还会因为
    筛选被重建成初始态而多刷一次。`PostsView` 已经监听了 route.query 做就地更新，
    key 必须把它放过去。
    """
    app = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    assert ':key="viewRoute.path"' in app
    assert "viewRoute.fullPath" not in app.split("<template>", 1)[1], (
        "模板里不能再按 fullPath 建 key"
    )


def test_article_rail_height_is_decoupled_from_the_reading_row():
    """左侧清单的高度不能参与阅读版式那一行的高度计算。

    清单天生可以很长。若让它像右侧目录那样直接撑开盒子，网格行高就跟着它走：
    30 条清单（实测 944px）配一篇只有一段的短文，会在正文之后空出几百像素只有
    左栏的留白（实测 327px），折叠清单时整页高度骤降、浏览器还会把读者的滚动位置
    夹回去（实测 scrollY 1400 → 1201）。所以外层盒子高 0、真正的面板绝对定位撑开：
    面板因此能占到「视口减去顶栏」的整段高度，文档高度却完全不受它影响。
    """
    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    rail = re.search(r"\.article-rail\s*\{([^}]*)\}", css, re.S)
    assert rail is not None, "找不到 .article-rail 基准规则"
    assert "height: 0;" in rail.group(1), "清单外层盒子必须不占高度"
    assert "max-height" not in rail.group(1), "高度上限不能压在参与行高计算的那一层"

    panel = re.search(r"\.article-rail__body,\s*\r?\n\s*\.article-rail__spine\s*\{([^}]*)\}", css, re.S)
    assert panel is not None, "展开态与折叠态的面板需要同一条定位规则"
    assert "position: absolute" in panel.group(1)

    body = re.search(r"\.article-rail__body\s*\{([^}]*)\}", css, re.S)
    assert body is not None
    assert "max-height: var(--panel-avail, calc(100vh - 8.5rem))" in body.group(1), (
        "面板高度由脚本给出（视口与区域末端的较小值），按正文高度收窄会让长清单只剩几行"
    )

    view = Path("frontend/src/views/PostView.vue").read_text(encoding="utf-8")
    assert ":body-ref" not in view, "清单高度已与正文解耦，不需要再传正文元素进来"


def test_short_viewport_footer_rule_comes_after_the_equal_specificity_base():
    """矮视口档位的页脚内距必须排在同特异性的基准之后。

    `:has()` 的特异性按其中权重最高的参数计算，因此
    `.print-shell:has(> .print-main > .print-subpage) > .print-colophon.site-footer`
    与 `@media (max-height: 780px)` 里的 `.print-shell.page-theme-articles > ...`
    特异性相同（都是 (0,2,0)），胜负完全由源码顺序决定。矮屏档位一旦排在前面就会被
    静默吃掉——实测 1366×768 下页脚读到 1.2rem 而非本档的 0.9rem，且不报错。
    """
    footer_css = Path("frontend/src/styles/footer.css").read_text(encoding="utf-8")
    layout_css = Path("frontend/src/styles/layout.css").read_text(encoding="utf-8")

    base = footer_css.index("padding-top: clamp(1.2rem, 2.8svh, 3.6rem) !important")
    knee = footer_css.index("@media (max-height: 780px)")
    assert knee > base, "矮视口页脚档位必须排在基准之后，否则被同特异性规则吃掉"
    assert "padding-top: 0.9rem !important" in footer_css[knee:]

    # 矮屏页脚档位只能存在于 footer.css：layout.css 排在它前面，放那里会被吃掉。
    # layout.css 里的 `.print-colophon.site-footer` 是基础版式（非 padding 覆盖），
    # 这里只断言它没有夹带 `!important` 的页脚内距覆盖。
    for rule in re.findall(r"\{([^}]*)\}", layout_css):
        if "print-colophon" in rule or "site-footer" in rule:
            assert "!important" not in rule, (
                f"layout.css 不应出现页脚内距的 !important 覆盖（会被 footer.css 的基准吃掉）：{rule[:80]}"
            )


def test_reveal_safety_net_does_not_pre_reveal_scroll_targets():
    """`.rv` 的兜底放行不能把还没进入视口的内容提前标成 `.vis`。

    兜底一旦无条件执行，`markVisible` 会把屏外元素也标成 `.vis`，而观察器只处理
    `.rv:not(.vis)`，于是「滚动到它们时」不再有入场动效（实测首页第 2/3 版共 7 个
    元素在翻页前就已被揭示）。因此兜底必须先确认观察器是否真的工作过。
    """
    reveal = Path("frontend/src/composables/useReveal.js").read_text(encoding="utf-8")
    assert "sawIntersection" in reveal, "兜底需要依据观察器是否产生过交集"
    assert "if (sawIntersection) return;" in reveal, (
        "兜底在观察器已正常工作时应直接返回，避免提前揭示屏外内容"
    )
    assert "sawIntersection = true;" in reveal


def test_stagger_delay_is_capped():
    """阶梯延迟必须有上限。

    未声明 `data-reveal-delay` 的元素按「揭示序号 × staggerMs」计算，序号在整页
    范围内累加；长文章里这类元素一多，延迟会涨到数秒，表现为内容迟迟不出现
    （实测长文章页在 5s 后仍有元素未淡入）。这里锁住上限的存在。
    """
    reveal = Path("frontend/src/composables/useReveal.js").read_text(encoding="utf-8")
    assert "MAX_STAGGER_STEPS" in reveal
    assert "Math.min(staggerIndex, MAX_STAGGER_STEPS)" in reveal


def test_motion_is_on_by_default_regardless_of_system_preference():
    """入场动效默认开启，不因系统 `prefers-reduced-motion` 而整站停用。

    本站以视觉呈现为主，动效属于版式的一部分：页面切换就应当播放。因此
    `motionDisabled()` 只认手动开关，媒体查询只在应用接管前（`html:not(.app-ready)`）
    作为无 JS 兜底存在。
    """
    reveal = Path("frontend/src/composables/useReveal.js").read_text(encoding="utf-8")
    motion_fn = reveal.split("export function motionDisabled()", 1)
    assert len(motion_fn) == 2, "找不到 motionDisabled()"
    body = motion_fn[1].split("\n}", 1)[0]
    assert "MOTION_STORAGE_KEY" in body
    assert "prefers-reduced-motion" not in body, (
        "motionDisabled() 不应再读取系统偏好——动效默认开启"
    )

    # CSS 兜底必须限定在应用接管之前，否则系统开关会整站抹掉动效
    for name in ("feedback.css", "layout.css", "home.css"):
        css = Path("frontend/src/styles", name).read_text(encoding="utf-8")
        if "prefers-reduced-motion" in css:
            assert "html:not(.app-ready)" in css, f"{name} 的 reduced-motion 兜底缺少 html:not(.app-ready)"

    # main.js 必须在挂载前打上 app-ready
    main = Path("frontend/src/main.js").read_text(encoding="utf-8")
    assert 'classList.add("app-ready")' in main


def test_no_motion_toggle_button_in_header():
    """站头不再提供动效开关（动效默认开启，无需 UI 入口）。"""
    header = Path("frontend/src/components/SiteHeader.vue").read_text(encoding="utf-8")
    assert "toggleMotion" not in header
    assert "print-nav__motion" not in header
    css = Path("frontend/src/styles/header.css").read_text(encoding="utf-8")
    assert "print-nav__motion" not in css


def test_cover_reveal_waits_for_the_initial_loader():
    """首屏封面必须等加载页离场后再入场。

    加载页整屏遮挡约 1.55s；封面若在被遮挡期间就入场，用户揭开时看到的只是最终态
    （实测标题单字在覆盖层内已从 op=0 走到 op=9、位移归零，观感就是「标题没有动效」）。
    做法：`.focused-cover` 的 `.rv` 与逐字浮现单字在 `html:not(.loader-done)` 期间
    被按在基准态并关掉过渡；`loader-done` 由 App 在加载页离场时加上。
    """
    css = Path("frontend/src/styles/feedback.css").read_text(encoding="utf-8")
    hold = css.split("html:not(.loader-done) .focused-cover .rv", 1)
    assert len(hold) == 2, "找不到「加载页期间按住封面」的规则"
    assert "opacity: 0 !important" in hold[1]
    assert "transition: none !important" in hold[1]
    # 必须连逐字浮现的单字一起按住：父级透明不会阻止子元素自身的动画推进
    assert "html:not(.loader-done) .focused-cover .split-text__char" in css

    app = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    assert 'classList.add("loader-done")' in app, "App 需要在加载页离场时加上 loader-done"
    assert 'InitialLoader @ready="onLoaderReady"' in app, "需要接住加载页的 ready 事件"


def test_split_char_uses_a_keyframe_animation():
    """逐字浮现必须用 keyframes，且靠「换动画名」来重播。

    用 transition 时无法可靠重播：同一个任务里摘掉再加回 `.vis`，浏览器在帧末算出的
    净状态没有变化，过渡不会启动（实测加了强制 reflow 也无效，1s 内位移恒为终值）。
    keyframes 则在 `.vis` 重新挂上、或 `animation-name` 变化时一定从头播。
    另外换名必须「每次重播只前进一格」——按元素逐个前进时，元素个数若是名字个数的
    整数倍（首页封面 9 个单字 × 3 个名字）会绕回同名，动画同样不会重启。
    """
    css = Path("frontend/src/styles/feedback.css").read_text(encoding="utf-8")
    assert "@keyframes split-char-rise" in css
    assert "animation: var(--rise-name, split-char-rise)" in css
    # 三组同内容不同名的 keyframes 供轮换
    for suffix in ("", "-b", "-c"):
        assert f"@keyframes split-char-rise{suffix}" in css

    reveal = Path("frontend/src/composables/useReveal.js").read_text(encoding="utf-8")
    assert "RISE_ANIMATIONS" in reveal
    assert 'setProperty("--rise-name"' in reveal
    # 每次重播只前进一格（在 forEach 之外）
    bump = reveal.split("function replayCharAnimations", 1)[1].split("}", 1)[0]
    assert "animSeq = (animSeq + 1)" in bump
    assert bump.index("animSeq = (animSeq + 1)") < bump.index("forEach")


def test_char_animation_endpoints_share_one_transform_function():
    """入场动画的首尾必须使用同一个 transform 函数名。

    构建时的 CSS 压缩器会把 `translate3d(0,0,0)` 改写成 `translateZ(0)`
    （压缩产物里实测存在 translateZ，而源码中根本没有）；函数名不一致时无法插值，
    整段退化为离散跳变——单字「啪」地出现而不是滑入，读起来就是卡顿。
    """
    css = Path("frontend/src/styles/feedback.css").read_text(encoding="utf-8")
    block = css.split("@keyframes split-char-rise {", 1)[1].split("\n}", 1)[0]
    assert "translateY(88%)" in block
    assert "translateY(0)" in block
    assert "translate3d" not in block, "首尾不要混用 translate3d / translateY"


def test_public_csp_allows_the_designed_webfonts():
    """公开页 CSP 必须放行 Google Fonts。

    否则公开页会静默退回 Georgia 等系统字体，与开发环境（Vite 不设 CSP）排印不一致
    ——实测同一视口下标题宽度 366px vs 354px，整页行高与断行都跟着变，
    属于「同一份代码两种样子」。
    """
    security = Path("backend/src/blog/security.py").read_text(encoding="utf-8")
    assert "https://fonts.googleapis.com" in security, "style-src 需要放行 Google Fonts 样式表"
    assert "https://fonts.gstatic.com" in security, "font-src 需要放行字体文件域"


def test_route_change_replays_entry_animation():
    """每次页面切换都要重播入场动效，不能只在首次加载时出现。

    路由视图虽然用 `:key` 强制重建，但重建后的元素初始就在视口内时，观察器回调
    与 Vue 补丁存在竞态，会出现「切回来是静止的」。需要在过渡结束后显式重播。
    """
    app = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    assert "replayPageReveal" in app, "App.vue 需要在页面切换后重播入场动效"
    assert '@after-enter="replayPageReveal"' in app, "重播应挂在过渡结束时机上"
    assert "replayReveal" in app, "需要从 useReveal 取用重播能力"

    reveal = Path("frontend/src/composables/useReveal.js").read_text(encoding="utf-8")
    assert "function replayReveal(" in reveal
    # 重播必须同时换动画名，否则逐字浮现不会重启
    assert "replayCharAnimations(root)" in reveal


def test_latest_page_shows_a_lead_plus_two_secondary_posts():
    """第 2 版是「头版头条 + 两篇次要稿」的主从版面。

    头条沿用原有的大版式（HomeFeature）；次要稿用同一套排版语言（分类行 / 标题 / 摘要 /
    元信息，复用 `.art__t` / `.art__p` / `.art__meta`）但整体缩小一档，
    因此标题最大字号必须明显小于头条，形成清晰的主从关系。
    """
    home = Path("frontend/src/views/HomeView.vue").read_text(encoding="utf-8")
    assert "HomeLatestRow" in home, "第 2 版需要渲染次要稿件行"
    assert "HomeFeature" in home, "头条保留原有大版式"
    assert "LATEST_FETCH_LIMIT = 3" in home, "取数要覆盖头条 + 2 篇次要稿"
    assert "secondaryPosts" in home

    row = Path("frontend/src/components/home/HomeLatestRow.vue").read_text(encoding="utf-8")
    # 复用头条的排版类，保证是「同一套版式」
    for cls in ("art__t", "art__p", "art__meta"):
        assert cls in row, f"次要稿应复用 {cls} 以保持同一套版式"
    # 没有封面图时不渲染空图槽
    assert 'v-if="post.cover_image"' in row

    css = Path("frontend/src/styles/pages.css").read_text(encoding="utf-8")
    card_title = re.search(r"\.home-secondary-card \.art__t \{[^}]*font-size:\s*clamp\(([^)]+)\)", css, re.S)
    assert card_title, "找不到次要稿标题的字号规则"
    assert card_title.group(1).strip().startswith("1rem"), "次要稿标题应从 1rem 起，明显小于头条"
    # 列数按实际稿件数收缩
    assert "repeat(var(--row-cols, 2)" in css
    assert "--row-cols" in row
    # 「仅一篇」分支走 .is-single 类，不用内联样式属性选择器（后者依赖声明文本，很脆）
    assert "is-single" in row and "is-single" in css
    assert "[style*=" not in css, "不要用内联样式属性选择器分支布局"

    # 缩略图按 4:3 出图。若只定宽并撑满行高，矮屏下会得到 112×52 的信箱式裁切，
    # 封面被截成一条横带；aspect-ratio + height 才能稳定拿到 4:3。
    thumb = re.search(r"\.home-secondary-card__thumb \{([^}]*)\}", css, re.S)
    assert thumb, "找不到缩略图规则"
    assert "aspect-ratio: 4 / 3" in thumb.group(1)
    assert "height: clamp(" in thumb.group(1)
    assert "width: clamp(" not in thumb.group(1)

    # 两篇并排时竖线由中缝分隔条承担，不能贴到缩略图上
    card_rule = re.search(r"\n\.home-secondary-card \{([^}]*)\}", css, re.S)
    assert card_rule, "找不到次要稿卡片规则"
    assert "border-right" not in card_rule.group(1)
    assert ":not(.is-single) .home-secondary-card + .home-secondary-card::before" in css


def test_home_sections_about_and_articles_drop_the_section_number():
    """首页第 2/3 版、关于页与文章目录都不再使用版次编号（`.sec-hd__n`）。

    这些小节序号（02 / 03 / 03 / 02）属于冗余装饰：首页版次已由右侧轨道表达，
    关于页是单页无序号可言，文章目录也只有一页目录。
    「下一篇」/404 仍需要它，所以基础的 `.sec-hd__n` 样式必须保留。
    """
    for name in ("HomeView", "AboutView", "PostsView"):
        src = Path(f"frontend/src/views/{name}.vue").read_text(encoding="utf-8")
        assert 'class="sec-hd__n"' not in src, f"{name} 的版次编号应已移除"
        # 标题与分隔线保留，页头结构不变
        assert "sec-hd__t" in src and "sec-hd__line" in src

    home = Path("frontend/src/views/HomeView.vue").read_text(encoding="utf-8")
    assert "最近更新 Latest" in home and "热点文章 Most Read" in home
    posts = Path("frontend/src/views/PostsView.vue").read_text(encoding="utf-8")
    assert "文章 Articles" in posts

    # 仍然需要编号的地方不能一起删掉
    related = Path("frontend/src/components/post/RelatedPostsGrid.vue").read_text(encoding="utf-8")
    assert 'class="sec-hd__n"' in related, "「下一篇」标注仍在使用"
    footer = Path("frontend/src/styles/footer.css").read_text(encoding="utf-8")
    assert ".sec-hd__n {" in footer and ".sec-hd__n::after" in footer

    # 这四处专属的着色规则已成死代码，应一并清理
    for dead in (
        ".home-latest-section .sec-hd__n",
        ".home-hot-section .sec-hd__n",
        ".page-theme-about .sec-hd__n",
        ".unified-posts-page .sec-hd__n",
    ):
        assert dead not in footer, f"{dead} 已无对应元素"


def test_home_rail_labels_use_names_instead_of_issue_numbers():
    """右侧版次轨道的可见标签用「首页 / 最近 / 热点」，不用 001/002/003。

    数字对读者没有意义；标签换成栏目名后，轨道也能自解释。
    无障碍名仍保留「第 N 版 · 栏目」以便与版面结构对应。
    """
    rail = Path("frontend/src/components/home/HomePageRail.vue").read_text(encoding="utf-8")
    for label in ("首页", "最近", "热点"):
        assert f'label: "{label}"' in rail, f"轨道应有「{label}」标签"
    for gone in ("001", "002", "003"):
        assert f'label: "{gone}"' not in rail, f"轨道不应再出现编号 {gone}"
    # 无障碍名与悬停提示仍指向版次与栏目
    assert "第 ${page.index + 1} 版 · ${page.name}" in rail
    assert '":title="' not in rail and ":title=" in rail
    # 刻度盒宽度固定，悬停只伸缩线本身，轨道总宽不随悬停变化
    assert "width: 26px" in rail


def test_posts_page_is_a_single_year_grouped_index():
    """文章目录只有一种形态：按年份分组的编年索引。

    原先「最新 / 归档 / 标签」三套视图装的是同一批文章，读者要先做一次与内容
    无关的选择。合并后：视图切换器消失，筛选改为按「栏目」，年份由 68px 展示级
    大字降为分节横杆。筛选按栏目而不是标签——标签会随写作无限生长。
    """
    view = Path("frontend/src/views/PostsView.vue").read_text(encoding="utf-8")
    assert "article-view-switch" not in view and "VIEW_OPTIONS" not in view
    assert "activeView" not in view, "视图维度应已取消"
    # 只剩索引一个分支
    assert view.count("<ArchiveLedger") == 1
    assert "v-else" in view
    # 筛选走服务端（category 查询参数），因此筛选与翻页可以并存
    assert "params.category = selectedCategory.value" in view
    assert "query.cat = selectedCategory.value" in view
    assert "route.query.cat" in view

    # 前台筛选按「栏目」而不是标签
    assert "selectedTag" not in view, "目录不再按标签筛选"
    assert "site.value?.categories" in view
    toolbar = Path("frontend/src/components/posts/PostsToolbox.vue").read_text(encoding="utf-8")
    assert "article-cat-filter" in toolbar and "cat-filter-button" in toolbar
    assert "tag-filter-button" not in toolbar
    # 搜索提示要说明关键词也能搜（关键词本身不展示）
    assert "关键词" in toolbar
    # 篇数必须来自服务端：按「当前已加载的文章」现算，筛选后其余栏目会显示成 0 篇
    assert "site.value?.categories" in view and "count" in view

    # buildQueryString 是显式白名单，漏掉新维度会静默丢掉筛选参数
    api = Path("frontend/src/services/api.js").read_text(encoding="utf-8")
    assert 'search.set("category", params.category)' in api

    # 已退休的两个视图组件不应残留
    for gone in ("PostLatestList", "TagResultsGrid"):
        assert not Path(f"frontend/src/components/posts/{gone}.vue").exists(), f"{gone} 应已下线"
        assert gone not in view

    # 索引行必须带摘要与阅读时长，否则读者无法从标题判断值不值得点开
    ledger = Path("frontend/src/components/posts/ArchiveLedger.vue").read_text(encoding="utf-8")
    assert "archive__excerpt" in ledger and "archive__read" in ledger
    assert "archive__year-rule" in ledger and "archive__badge" in ledger

    css = Path("frontend/src/styles/posts.css").read_text(encoding="utf-8")
    # 栏目胶囊
    assert ".cat-filter-button" in css
    assert "tag-filter-button" not in css
    # 年份不再是展示级大字
    year_fs = re.search(r"\.archive__year span \{\s*font-size:\s*clamp\(([^)]+)\)", css)
    assert year_fs and float(year_fs.group(1).split(",")[0].strip().rstrip("rem")) <= 1.6
    # 限宽用 em 而非 ch：等宽字体下 1ch 只有约 0.6em，中文占满一个 em
    assert "max-width: min(100%, 26em)" in css
    assert "max-width: min(100%, 52em)" in css

    # 退休选择器不能再出现在任何样式文件里（含诸如同权重覆盖用的前缀写法）
    dead = ("article-view-switch", "article-view-button", "unified-archive-view",
            "unified-tags-view", "unified-latest-list", "print-list-item",
            "print-article-list", "print-tag-results", "article-item__thumb",
            "article-tag-filter", "tag-filter-button", "article-search__label")
    for path in Path("frontend/src/styles").glob("*.css"):
        text = path.read_text(encoding="utf-8")
        for token in dead:
            assert token not in text, f"{path.name} 仍残留已下线选择器 {token}"


def test_posts_endpoint_always_returns_the_same_envelope(app_bundle):
    """`/api/posts` 只有一种载荷形状，永远带信封。

    早先「不带 page」会返回裸数组：同一个端点两种形状，前端每处调用都得先写
    `Array.isArray(list) ? list : list.items`，测试也得记住哪条路径是哪种形状。
    现在缺省即 page=1，per_page 沿用它原有的缺省（带 page 是 10、不带是 50，同为 50 上限），
    total/has_more 一并给出。
    """
    _application, store = app_bundle
    client = _application.test_client()
    for index in range(3):
        store.save_post(
            {
                "title": f"信封 {index}",
                "slug": f"envelope-{index}",
                "category": "工程",
                "markdown_content": "正文一段。",
            },
            action="published",
        )

    envelope = {"items", "total", "page", "per_page", "has_more"}
    bare = client.get("/api/posts").get_json()
    assert set(bare) == envelope, "不带 page 也必须返回信封"
    assert bare["page"] == 1 and bare["per_page"] == 50 and bare["total"] == 3
    assert len(bare["items"]) == 3 and bare["has_more"] is False

    limited = client.get("/api/posts?limit=1").get_json()
    assert set(limited) == envelope
    assert len(limited["items"]) == 1 and limited["total"] == 3 and limited["has_more"] is True

    paged = client.get("/api/posts?page=2").get_json()
    assert set(paged) == envelope
    assert paged["page"] == 2 and paged["per_page"] == 10


def test_article_rail_scope_is_switchable_and_truthful():
    """左栏的表头是一个范围切换器，不是一块写死的标签。

    需求：读者除了「最新」还应该能选别的范围，但不能臃肿。所以选项收进菜单，表头只占
    一个词的位置；勾选与表头都读「当前装载的范围」，于是本栏目太薄退化为最新时标签写实、
    菜单里再说明本栏目只剩自己。菜单里「本栏目」发出的 key 是栏目名而不是空串：读者
    明确点了它，就不该再被「本栏目太薄→退化为最新」这条默认策略顶掉。
    """
    rail = Path("frontend/src/components/post/PostRail.vue").read_text(encoding="utf-8")
    assert 'class="article-rail__scope"' in rail and 'aria-haspopup="menu"' in rail
    assert 'role="menuitemradio"' in rail and ':aria-checked=' in rail
    assert "select-scope" in rail, "切换范围要能上抛给视图层"
    assert "key: follow," in rail, "本栏目这一项必须发栏目名，否则显式选择会被默认策略覆盖"
    assert 'hint: count > 1 ? String(count) : "仅此一篇"' in rail

    store = Path("frontend/src/composables/usePostRail.js").read_text(encoding="utf-8")
    assert "const railScope = ref" in store and "function setRailScope" in store
    assert "MIN_SCOPE_POSTS = 2" in store, "本栏目只要还有一篇别的文章就照列"
    # 显式选择不做退化：只有「跟随当前文章」那条路径才允许回落到最新
    explicit = re.search(r"function loadExplicitScope\(scope\) \{(.*?)\n\}", store, re.S)
    assert explicit is not None
    assert 'mode: "latest"' in explicit.group(1)
    assert "MIN_SCOPE_POSTS" not in explicit.group(1), "显式选择不该再做厚薄判断"

    view = Path("frontend/src/views/PostView.vue").read_text(encoding="utf-8")
    assert '@select-scope="setRailScope"' in view
    assert ":follow-category=" in view and ":categories=" in view

    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    assert ".article-rail__scopes" in css and ".article-rail__scope-option" in css
    assert "var(--panel-avail" in css.split(".article-rail__scopes")[1][:400], (
        "菜单高度要跟着面板可用高度走，否则短面板下菜单会比面板还高"
    )


def test_collapsed_spines_carry_no_numbers():
    """折叠后的书脊只留箭头与竖排名称，不再挂数字。

    两条书脊的数字含义互不相干（目录是当前章节号、清单是总篇数），并排放着读者无从
    分辨，去掉后左右视觉一致。
    """
    rail = Path("frontend/src/components/post/PostRail.vue").read_text(encoding="utf-8")
    toc = Path("frontend/src/components/post/PostToc.vue").read_text(encoding="utf-8")
    for name, src in (("PostRail", rail), ("PostToc", toc)):
        spine = re.search(r'class="article-(?:rail|toc)__spine"(.*?)</button>', src, re.S)
        assert spine is not None, f"{name} 找不到书脊按钮"
        assert "<strong>" not in spine.group(1), f"{name} 的书脊不应再有数字"

    css = Path("frontend/src/styles/post.css").read_text(encoding="utf-8")
    assert ".article-toc__spine strong" not in css, "书脊数字的样式应一并删除"
    assert ".article-rail__spine strong" not in css
    # 折叠态右书脊要与左书脊同高：展开态那段上内距必须归零
    assert re.search(r"\.article-toc\.is-collapsed \{[^}]*padding-top: 0", css, re.S) is not None


def test_article_tag_chips_lead_to_a_search_that_actually_works():
    """文章页的标签要成为能生效的入口，而不是点了没反应的链接。

    标签不参与目录筛选（前台只有「栏目」一个筛选维度，见上一个测试），所以标签链接
    走检索维度 `q`——服务端会匹配标题/摘要/标签/关键词。此前它指向 `?tag=…`，而目录页
    只读 q/cat/page，参数被静默丢掉、URL 随后被规范化回 /posts，点了等于没点
    （实测：点「链表」→ URL 变 /posts，全部胶囊高亮，2 篇全列）。
    """
    hero = Path("frontend/src/components/post/PostHero.vue").read_text(encoding="utf-8")
    assert "posts?tag=" not in hero, "标签链接不能再用目录页不解析的 tag 参数"
    assert "query: { q: tag }" in hero, "标签链接应走检索维度 q"

    # 顺带锁住重复取数：初次进入 ?q=… 时 route state 已经取过一次，
    # normalizedQuery 的防抖 watcher 必须跳过 application 阶段，否则同一 key 请求两遍
    # ——scheduleReload 是强制取数，绕过了 fetchList 的去重。
    view = Path("frontend/src/views/PostsView.vue").read_text(encoding="utf-8")
    watcher = re.search(r"watch\(normalizedQuery, \(\) => \{(.*?)\n\}\)", view, re.S)
    assert watcher is not None, "找不到 normalizedQuery 的防抖 watcher"
    assert "applyingRouteState" in watcher.group(1), (
        "初次应用 route state 时不应再触发一次搜索取数"
    )

def test_keywords_are_searchable_but_never_rendered(app_bundle):
    """关键词只用于检索，不出现在任何对外载荷里。

    标签有展示价值，但会把文章归到一两个具体名词上；关键词承担的是「别名 / 同义词 /
    英文写法」这类只为命中的信息，露在页面上只会添乱，所以不进列表载荷、不进站点载荷、
    也不进文章详情。
    """
    _application, store = app_bundle
    store.save_post(
        {
            "title": "两数相加",
            "slug": "two-sum",
            "markdown_content": "## 思路\n\n用哈希表记录补数。",
            "excerpt": "一道入门题",
            "category": "算法",
            "tags": "链表",
            "keywords": "哈希表, two sum, 补数",
            "published_at": "2026-01-01",
            "read_time": "4 min",
        },
        action="published",
    )

    # 命中关键词（含英文与中文别名）
    for query in ("哈希表", "two sum", "补数"):
        hits = store.list_posts(search=query)
        assert [post["slug"] for post in hits] == ["two-sum"], f"{query} 应能检索到文章"

    # 列表载荷与详情都不带 keywords
    row = store.list_posts()[0]
    assert "keywords" not in row
    assert "keywords" not in summarize_post(row)
    detail = build_post_detail_payload(
        store.get_post_by_slug("two-sum"), related_posts=[], previous_post=None, next_post=None
    )
    assert "keywords" not in detail

    # 站点载荷只暴露 tags/categories，不暴露关键词
    payload = store.get_site_payload()
    assert "keywords" not in payload
    assert payload["categories"] == [{"name": "算法", "count": 1}]
    assert payload["tags"] == ["链表"]

    # 后台编辑载荷需要能回填关键词
    editable = build_edit_post(store.get_post_by_slug("two-sum", include_drafts=True))
    assert editable["keywords"] == ["哈希表", "two sum", "补数"]
    assert editable["keywords_text"] == "哈希表, two sum, 补数"


def test_public_api_filters_by_category_and_searches_keywords(client, app_bundle):
    """公开接口支持 category 过滤 + 关键词检索，并对栏目给出篇数排序。"""
    _application, store = app_bundle
    for index, (category, keywords) in enumerate(
        [("算法", "双指针"), ("算法", "剪枝"), ("工程", "Nginx")]
    ):
        store.save_post(
            {
                "title": f"文章 {index}",
                "slug": f"post-{index}",
                "markdown_content": "## 小节\n\n正文内容若干。",
                "excerpt": "摘要",
                "category": category,
                "tags": "通用",
                "keywords": keywords,
                "published_at": f"2026-0{index + 1}-01",
                "read_time": "3 min",
            },
            action="published",
        )

    site = client.get("/api/site").get_json()
    # 篇数多的栏目排前面，且只列出真实用过的栏目；篇数由服务端统计
    assert site["categories"] == [
        {"name": "算法", "count": 2},
        {"name": "工程", "count": 1},
    ]

    only_algo = client.get("/api/posts?category=算法").get_json()["items"]
    assert sorted(item["slug"] for item in only_algo) == ["post-0", "post-1"]
    assert all("keywords" not in item for item in only_algo)

    by_keyword = client.get("/api/posts?q=剪枝").get_json()["items"]
    assert [item["slug"] for item in by_keyword] == ["post-1"]

    # 分页与筛选并存（count 也要带上 category，否则 total 会算成全量）
    paged = client.get("/api/posts?category=算法&page=1&limit=1").get_json()
    assert paged["total"] == 2
    assert len(paged["items"]) == 1
    assert paged["has_more"] is True


def test_category_is_locked_to_the_preset_vocabulary(app_bundle):
    """栏目是固定词表：只允许预设里的几个值。

    前台唯一的粗粒度筛选维度就是栏目。放开自由录入，筛选条迟早会长成第二个标签云，
    所以这里是硬校验（发布前拦截 + 写入时拒绝），而不是「提示但不拦」。
    """
    _application, store = app_bundle
    base = {
        "title": "标题",
        "markdown_content": "## 小节\n\n" + "内容" * 120,
        "excerpt": "摘要",
        "tags": "标签",
        "cover_image": "/uploads/media/x.png",
    }

    # 预设内通过
    for preset in CATEGORY_PRESETS:
        result = store.validate_post_for_publish({**base, "category": preset})
        assert result["ok"] is True, f"{preset} 应当可以发布"
        assert "invalid_category" not in {item["code"] for item in result["errors"]}

    # 发布预检（后台发布按钮就读它）必须拦住预设外的栏目
    bad = store.validate_post_for_publish({**base, "category": "随手一写"})
    errors = {item["code"]: item["message"] for item in bad["errors"]}
    assert "invalid_category" in errors
    assert bad["ok"] is False
    assert CATEGORY_PRESETS[0] in errors["invalid_category"]

    # 留空仍是「建议填写」，不算错误
    empty = store.validate_post_for_publish({**base, "category": ""})
    assert "invalid_category" not in {item["code"] for item in empty["errors"]}
    assert "missing_category" in {item["code"] for item in empty["warnings"]}

    # 写入路径（导入的 frontmatter、历史存量）不硬拦：约束落在「发布」这道门上，
    # 由后台的固定下拉框 + 发布预检共同保证对外可见的栏目只来自词表。
    draft_id = store.save_post(
        {**base, "slug": "draft-cat", "category": "随手一写"}, action="draft"
    )
    assert store.get_post_by_id(draft_id)["category"] == "随手一写"


def test_admin_category_field_is_a_fixed_select(client, app_bundle):
    """后台的栏目控件是下拉选择，不是自由输入；标签仍然自由录入。"""
    login(client)
    page = client.get("/admin/write").get_data(as_text=True)
    assert '<select name="category"' in page
    assert 'name="category"' in page and 'type="text" name="category"' not in page
    for preset in CATEGORY_PRESETS:
        assert f'<option value="{preset}"' in page, f"下拉框应包含预设栏目 {preset}"
    # 旧的自定义 datalist 已由固定下拉框取代
    assert 'id="category-suggestions"' not in page
    # 标签仍是自由输入
    assert 'type="text" id="tags"' in page
    # 关键词输入也在
    assert 'name="keywords"' in page


def test_route_replay_does_not_restart_a_running_char_animation():
    """路由切换后的重播，不能把已经在播的逐字浮现从半途重启。

    新建的视图一挂载就落在视口内，观察器会立刻把封面标题标成 `.vis`，单字动画随即
    开跑；过渡结束后的重播若再换一次动画名，就会把这几个字清零重来——观感正是
    「从文章页/关于页切回封面页时标题渲染了两遍」（实测重播时刻「至/知」的
    currentTime 已走到 261ms，换名后被重置为 0，不重复的下标也从 9 变成 11）。

    但整屏翻页必须保留重播（单字动画那时早已播完），所以这个判断只能是入口级选项。
    """
    reveal = Path("frontend/src/composables/useReveal.js").read_text(encoding="utf-8")
    assert "function charEntranceRunning(" in reveal
    assert 'animation.playState === "running"' in reveal
    assert "replayReveal(root, { skipRunningCharAnimation = false } = {})" in reveal
    # 命中时只标已揭示，必须在「摘掉 .vis」之前就返回，
    # 否则容器的入场会重来而单字继续播，两侧时序错位。
    guard = reveal.index("skipRunningCharAnimation && charEntranceRunning(root)")
    detach = reveal.index("targets.forEach((el) => el.classList.remove(\"vis\"));")
    assert guard < detach, "已在播的判断必须早于摘除 .vis"

    app = Path("frontend/src/App.vue").read_text(encoding="utf-8")
    assert "skipRunningCharAnimation: true" in app, "路由切换入口应跳过已在播的逐字动画"

    # 翻页入口不得带上这个选项：切回封面（含从第 2/3 版切回）必须重播。
    home = Path("frontend/src/views/HomeView.vue").read_text(encoding="utf-8")
    assert "await replayReveal(sections[page]);" in home
    assert "skipRunningCharAnimation" not in home


def test_no_unused_css_classes():
    """样式表里不该留下没人用的类。

    这类死代码一次清理之后就容易被重新引入（改版换类名时旧的留着、删组件时忘了删规则），
    而且构建、运行、测试都不会报错。这里把「CSS 里定义、但模板/脚本里从未出现」当作失败，
    让它变成一道可持续的红线。

    三类例外不算死类：
    - Vue `<Transition>` 注入的 `page-fade-*`、Vue Router 的 `router-link-*`；
    - highlight.js 运行时生成的 `hljs-*`；
    - Jinja 用 f-string 拼出的 flash 类 `message--*`。
    `url(...)` 与注释要先抠掉：`data:image/svg+xml` 里的 `www.w3.org` 会被朴素正则读成
    `.org` / `.w3` 两个类名（实测踩过）。
    """
    skip_parts = {".git", ".venv", "node_modules", "dist", "__pycache__", ".tmp",
                  ".pytest_cache", "output", ".playwright-cli", ".codex", ".agents",
                  ".claude", ".run", "vendor"}

    def walk(base, exts):
        for path in Path(base).rglob("*"):
            if path.is_file() and path.suffix in exts and not any(p in skip_parts for p in path.parts):
                yield path

    corpus = "\n".join(
        [p.read_text(encoding="utf-8-sig") for p in walk("frontend/src", {".vue", ".js"})]
        + [p.read_text(encoding="utf-8-sig") for p in walk("backend/src/blog/templates", {".html"})]
        + [p.read_text(encoding="utf-8-sig") for p in walk("backend/src/blog/static/admin", {".js"})]
    )
    dynamic = re.compile(r"^(hljs-|page-fade-|router-link|message--)")

    offenders: list[str] = []
    for path in sorted(Path("frontend/src/styles").glob("*.css")):
        if path.name == "editorial.css":
            continue
        text = path.read_text(encoding="utf-8-sig")
        text = re.sub(r"url\((?:[^()]|\([^()]*\))*\)", "", re.sub(r"/\*.*?\*/", "", text, flags=re.S))
        for name in sorted(set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", text))):
            if name in corpus or dynamic.match(name):
                continue
            offenders.append(f"{path.name}: .{name}")
    assert not offenders, "存在无人使用的 CSS 类：\n  " + "\n  ".join(offenders)


def test_js_sources_have_no_stray_escaped_quotes():
    """JS/Vue/模板里不应出现 `\\'` 这种游离的转义单引号。

    自查出来的坑：用脚本批量改代码时，替换串里写了 `\\'`，结果把反斜杠原样带进了
    源码——`document.querySelector(\\'[name="x"]\\')`。它让**整个 ES 模块图解析失败**
    （一个模块语法错误会连带它所有的 importer），而后台写作台的 JS 只在浏览器里执行，
    服务端测试与构建都不会碰到，于是这类错误可以一路绿灯通过。

    JS 里单引号字符串内部确实会用到 `\\'`，所以这里只针对本项目实际不会出现的形态：
    引号紧跟在左括号/逗号/等号之后仍带反斜杠。
    """
    patterns = (".js", ".vue", ".html")
    offenders = []
    for path in sorted(Path(".").rglob("*")):
        if not path.is_file() or path.suffix not in patterns:
            continue
        if any(p in path.parts for p in (".git", ".venv", "node_modules", "dist", "__pycache__", ".tmp")):
            continue
        if "vendor" in path.parts or path.name.startswith("highlight.min"):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8-sig", errors="ignore").split("\n"), 1):
            if re.search(r"[\(\[=,]\s*\\['\"]", line):
                offenders.append(f"{path}:{number}: {line.strip()[:110]}")
    assert not offenders, "存在游离的转义引号：\n  " + "\n  ".join(offenders)


def test_stylesheets_have_no_orphaned_selector_fragments():
    """删除规则块时不能留下悬空的选择器行。

    形如 `.a:hover,` 后面直接跟空行再接 `.b { ... }`，浏览器会把 `.b` 并进同一条
    规则，静默改变另一处的样式——这类错误构建不报、测试不报，只能靠静态校验兜住。
    """
    for path in sorted(Path("frontend/src/styles").glob("*.css")):
        text = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        for match in re.finditer(r"([^{}]*)\{", text):
            selector = match.group(1).strip("\n")
            if not selector.strip():
                continue
            assert "\n\n" not in selector, f"{path.name} 存在悬空选择器：{selector.strip()[:80]}"


def test_posts_index_fits_one_screen_and_still_scrolls_when_long():
    """目录一页之内要把页脚一起收进首屏（与封面页、关于页一致）。

    原先尾部叠了三层留白（.posts-index 4rem + .print-year-block 3rem 级的
    .archive__list 2.5rem，实测 152px 纯空白），把页脚顶出折叠线。
    列表长到需要滚动时留白是呼吸，一屏放得下时它就只是碍事，所以改为按视口高度流式收紧。
    """
    css = Path("frontend/src/styles/posts.css").read_text(encoding="utf-8")

    # 尾部留白收敛
    assert re.search(r"\.unified-posts-page \.print-year-block \{\s*padding-bottom: 0;\s*\}", css)
    list_rule = re.search(r"\.unified-posts-page \.archive__list \{\s*margin-bottom: ([^;]+);", css)
    assert list_rule and "svh" in list_rule.group(1), "列表尾部内距应按视口高度流式收紧"

    # 矮视口分档存在
    assert "@media (max-height: 700px)" in css
    assert "@media (max-height: 620px)" in css

    # 关键顺序陷阱：`.unified-posts-page .archive__li` 与 `.posts-index .archive__li`
    # 同权重，分档里若只写 padding-top/bottom，会被后面那条整体 padding 简写吃掉，
    # 而且完全不报错（实测分档曾因此失效）。所以分档必须排在索引规则之后。
    tier = css.index("@media (max-height: 700px)")
    base_li = css.index(".posts-index .archive__li {")
    assert tier > base_li, "矮视口分档必须排在索引基础规则之后，否则会被同权重的 padding 简写静默覆盖"

    # 顶栏高度 68px 是 padding-top 的下限，否则章节标签会滑到报头底下
    top = re.search(r"@media \(max-height: 700px\) \{.*?\.unified-posts-page\.content-view \{\s*padding-top: clamp\(([^)]+)\)",
                    css, re.S)
    assert top, "矮视口分档应压低 .content-view 的顶部内距"
    assert float(top.group(1).split(",")[0].strip().rstrip("rem")) >= 4.5, "顶部内距不得低于顶栏高度"

    # 流式收紧只改内距，不得给容器引入裁切或限高（列表变长必须仍能正常滚动）。
    # 摘要的单行截断是文本级 -webkit-line-clamp，属于预期用法，这里只看容器。
    containers = (
        ".posts-index", ".print-year-ledger", ".print-year-block", ".archive__list",
        ".unified-posts-page", ".unified-posts-page.content-view",
    )
    for path in sorted(Path("frontend/src/styles").glob("*.css")):
        for rule in re.finditer(r"([^{}]+)\{([^}]*)\}", path.read_text(encoding="utf-8")):
            selector, body = rule.group(1).strip(), rule.group(2)
            if not any(selector == c or selector.startswith(c + " ") for c in containers):
                continue
            assert "overflow: hidden" not in body, f"{path.name} 不应给目录容器 {selector} 加裁切"
            assert "max-height" not in body, f"{path.name} 不应给目录容器 {selector} 限高（应让页面自然滚动）"


def test_home_flip_replays_reveal_for_target_page():
    """首页整屏翻页必须显式重播入场动效。

    翻页时正文不滚动，被切走的版面里 `.rv` 早已是 `.vis`，观察器不会再触发；
    而首次进入第 2/3 版时元素可能迟迟不被判定为相交（实测内容 op=0，要等 4s
    兜底才现形，看起来就是「翻过去是空白页」）。两种情形都要靠显式重播兜住。
    """
    home = Path("frontend/src/views/HomeView.vue").read_text(encoding="utf-8")
    assert "replayReveal" in home
    assert "watch([currentPage, isFlipActive]" in home, "需要在切版时触发重播"
    assert "nextTick" in re.search(r'^import \{([^}]+)\} from "vue";', home, re.M).group(1), (
        "watch 回调里用了 nextTick，必须从 vue 引入"
    )
    # 只重播刚进入的那一版：把「当前版 + 上一版」都重播会让封面在屏外空转一遍
    assert "replayReveal(sections[page])" in home


def test_motion_off_keeps_the_split_text_fade():
    """手动关闭动效时，逐字浮现要保留可见的显现过程，而不是直接闪出。

    历史写法是 `transition: none; opacity: 1; transform: none`，等于把品牌动效连同时长
    一起取消——实测加载页标题全程 op=1.00、无位移，开场节奏完全消失。
    现在这段动效改用 keyframes；降级时仍要求它「有可见的进行时」，
    而不是一帧之内直接到位。
    """
    css = Path("frontend/src/styles/feedback.css").read_text(encoding="utf-8")

    # 基准态必须保留位移起点，形成可见的滑动/淡入过程
    assert ".split-text__char {" in css
    assert "translateY(88%)" in css

    # 入场用 keyframes，首尾都要有 opacity 与 transform 的变化
    rise = css.split("@keyframes split-char-rise {", 1)[1].split("\n}", 1)[0]
    assert "opacity: 0" in rise and "opacity: 1" in rise
    assert "translateY(88%)" in rise and "translateY(0)" in rise

    # 手动关闭动效时不得把动画时长压成 0，也不得直接把 opacity 设为 1
    motion_off = re.findall(r"html\.motion-off [^{]*\.split-text__char[^{]*\{([^}]*)\}", css)
    for rule in motion_off:
        assert "opacity: 1" not in rule, "不得直接把 opacity 设为 1（会跳过逐字淡入）"
        assert "transition: none" not in rule


def test_import_normalizes_nbsp(app_bundle):
    _application, store = app_bundle

    class FakeFile:
        filename = "nbsp.md"

        def read(self):
            return "---\ntitle: NBSP Doc\n---\n\nHello\u00a0world".encode("utf-8")

    payload = store.import_markdown(FakeFile())
    assert "\xa0" not in payload["markdown_content"]
    assert "Hello world" in payload["markdown_content"]


def test_atom_feed_and_sitemap_and_robots(app_bundle, client, monkeypatch):
    _application, store = app_bundle
    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", "https://example.com")
    store.save_post(
        {
            "title": "Public Feed Post",
            "slug": "public-feed-post",
            "markdown_content": "Hello feed",
            "excerpt": "Feed excerpt",
            "published_at": "2099-04-01",
        },
        action="published",
    )
    store.save_post(
        {
            "title": "Draft Stay Hidden",
            "slug": "draft-stay-hidden",
            "markdown_content": "secret",
        },
        action="draft",
    )

    feed = client.get("/feed.xml")
    assert feed.status_code == 200
    assert "application/atom+xml" in feed.headers.get("Content-Type", "")
    body = feed.get_data(as_text=True)
    assert "Public Feed Post" in body
    assert "https://example.com/posts/public-feed-post" in body
    assert "Draft Stay Hidden" not in body
    import xml.etree.ElementTree as ET

    ET.fromstring(body)

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    sm = sitemap.get_data(as_text=True)
    assert "https://example.com/posts/public-feed-post" in sm
    assert "draft-stay-hidden" not in sm
    ET.fromstring(sm)

    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    robots_body = robots.get_data(as_text=True)
    assert "Sitemap: https://example.com/sitemap.xml" in robots_body
    assert "Disallow" not in robots_body


def test_post_page_injects_open_graph_meta(app_bundle, client, tmp_path, monkeypatch):
    application, store = app_bundle
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><html><head><title>至知</title>"
        '<meta name="description" content="default" />'
        "</head><body><div id=\"app\"></div></body></html>",
        encoding="utf-8",
    )
    import blog.app as app_module

    spa_module = importlib.import_module("blog.routes.spa")
    monkeypatch.setattr(spa_module, "FRONTEND_DIST", dist)
    monkeypatch.setattr(app_module, "FRONTEND_DIST", dist, raising=False)
    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", "https://example.com")
    # recreate app with patched FRONTEND_DIST
    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()
    store = app_module.BlogStore if False else store
    # store still points to tmp db from fixture; need same store path
    from blog.store import BlogStore
    # fixture store already has data path; save via fixture store then hit new app
    # Re-bind: create_app makes new BlogStore from env BLOG_DATABASE_PATH which fixture set.
    store = BlogStore()
    store.init()
    store.save_post(
        {
            "title": 'Title <script> & "quotes"',
            "slug": "og-post",
            "markdown_content": "body",
            "excerpt": 'Desc <b>x</b> & more',
            "cover_image": "/uploads/media/cover.jpg",
            "published_at": "2099-05-01",
        },
        action="published",
    )

    response = client.get("/posts/og-post")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "og:title" in html
    assert "Title &lt;script&gt; &amp; &quot;quotes&quot;" in html or "Title &lt;script&gt;" in html
    assert 'property="og:type" content="article"' in html
    assert "https://example.com/posts/og-post" in html
    assert "https://example.com/uploads/media/cover.jpg" in html
    assert "<script>" not in html.split("</head>")[0]

    missing = client.get("/posts/does-not-exist-slug")
    assert missing.status_code == 200
    missing_html = missing.get_data(as_text=True)
    assert "og:title" not in missing_html
    assert "<title>至知</title>" in missing_html


def test_image_pipeline_strips_exif_and_downscales(app_bundle, client):
    _application, store = app_bundle
    from PIL import Image as PILImage
    from PIL.ExifTags import Base as ExifBase

    big = PILImage.new("RGB", (3000, 1000), "#336699")
    # attach fake GPS-ish EXIF via piexif-less path: use info? Pillow JPEG exif needs encoded bytes.
    # Use simple exif dict if available
    exif = big.getexif()
    try:
        exif[271] = "TestCamera"  # Make
        exif[34853] = {1: "N", 2: (1, 1, 1), 3: "E", 4: (1, 1, 1)}  # GPSInfo-ish
    except Exception:
        pass
    buf = io.BytesIO()
    try:
        big.save(buf, format="JPEG", quality=95, exif=exif)
    except Exception:
        big.save(buf, format="JPEG", quality=95)
    buf.seek(0)

    class FakeStorage:
        filename = "phone.jpg"
        mimetype = "image/jpeg"
        stream = buf

    relative = store.save_file(FakeStorage(), "media")
    from blog.store import UPLOADS_DIR

    saved = (UPLOADS_DIR / relative).read_bytes()
    with PILImage.open(io.BytesIO(saved)) as out:
        assert max(out.size) <= 1920
        assert out.format == "JPEG"
        out_exif = out.getexif()
        # re-encoded JPEG should not keep original GPS dump
        assert not out_exif or 34853 not in out_exif

    # small PNG unchanged dimensions
    small_buf = io.BytesIO()
    PILImage.new("RGB", (32, 32), "#112233").save(small_buf, format="PNG")
    small_buf.seek(0)

    class FakePng:
        filename = "small.png"
        mimetype = "image/png"
        stream = small_buf

    rel_png = store.save_file(FakePng(), "media")
    with PILImage.open(UPLOADS_DIR / rel_png) as out_png:
        assert out_png.size == (32, 32)

    # uploads cache header
    token = login(client)
    upload_resp = client.post(
        "/admin/api/upload-image",
        data={"image": (image_bytes("JPEG"), "tiny.jpg")},
        headers={"X-CSRF-Token": token},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 200
    url = upload_resp.get_json()["url"]
    cached = client.get(url)
    assert cached.status_code == 200
    assert "max-age=31536000" in cached.headers.get("Cache-Control", "")
    assert "immutable" in cached.headers.get("Cache-Control", "")



def post_fields(title="Revision article", slug="revision-article", markdown="# Revision\n\n## Section\n\nBody text"):
    return {
        "title": title,
        "slug": slug,
        "markdown_content": markdown,
        "category": CATEGORY_PRESETS[0],
        "tags": "one, two",
        "excerpt": "A test excerpt",
    }


def test_manual_saves_create_revisions_but_autosave_does_not(app_bundle, client):
    _application, store = app_bundle
    token = login(client)
    response = client.post(
        "/admin/posts/save",
        data={"csrf_token": token, **post_fields(), "action": "draft"},
    )
    assert response.status_code == 302
    post_id = next(item["id"] for item in store.list_admin_posts() if item["title"] == "Revision article")
    assert len(store.list_post_revisions(post_id)) == 1

    current = store.get_post_by_id(post_id)
    autosave = client.post(
        "/admin/api/autosave",
        json={
            "post_id": post_id,
            "updated_at": current["updated_at"],
            "fields": {**post_fields(), "title": "Autosaved only"},
        },
        headers={"X-CSRF-Token": token},
    )
    assert autosave.status_code == 200
    assert len(store.list_post_revisions(post_id)) == 1

    published = client.post(
        "/admin/posts/save",
        data={
            "csrf_token": token,
            "post_id": post_id,
            **post_fields(title="Published revision", markdown="# Published\n\n## Section\n\nLong enough body"),
            "action": "published",
        },
    )
    assert published.status_code == 302
    revisions = store.list_post_revisions(post_id)
    assert len(revisions) == 2
    assert revisions[0]["revision_type"] == "published"


def test_trash_hides_post_and_restore_returns_draft(app_bundle, client):
    _application, store = app_bundle
    post_id = store.save_post(post_fields(), action="published")
    token = login(client)

    response = client.post(
        f"/admin/posts/{post_id}/delete",
        data={"csrf_token": token},
    )
    assert response.status_code == 302
    trashed = store.get_post_by_id(post_id)
    assert trashed["status"] == "trashed"
    assert trashed["deleted_at"]
    assert client.get(f"/api/posts/{trashed['slug']}").status_code == 404

    response = client.post(
        f"/admin/posts/{post_id}/restore",
        data={"csrf_token": token},
    )
    assert response.status_code == 302
    restored = store.get_post_by_id(post_id)
    assert restored["status"] == "draft"
    assert restored["deleted_at"] is None
    assert client.get(f"/api/posts/{restored['slug']}").status_code == 404


def test_revision_preview_and_restore_returns_draft(app_bundle, client):
    _application, store = app_bundle
    post_id = store.save_post(post_fields(title="First version"), action="draft")
    store.save_post(post_fields(title="Second version", markdown="# Second\n\n## Section\n\nBody"), post_id=post_id, action="draft")
    revisions = store.list_post_revisions(post_id)
    assert len(revisions) == 2
    oldest_id = revisions[-1]["id"]
    token = login(client)

    detail = client.get(f"/admin/api/posts/{post_id}/revisions/{oldest_id}")
    assert detail.status_code == 200
    assert detail.get_json()["snapshot"]["title"] == "First version"

    restored = client.post(
        f"/admin/api/posts/{post_id}/revisions/{oldest_id}/restore",
        json={},
        headers={"X-CSRF-Token": token},
    )
    assert restored.status_code == 200
    current = store.get_post_by_id(post_id)
    assert current["title"] == "First version"
    assert current["status"] == "draft"


def test_restore_revision_uniquifies_slug_on_collision(app_bundle):
    _application, store = app_bundle
    # Post A holds an early revision snapshotting slug "collide", then A moves off it.
    post_a = store.save_post(
        {"title": "A one", "slug": "collide", "markdown_content": "# A\n\nBody"},
        action="draft",
    )
    store.save_post(
        {"title": "A two", "slug": "a-two-new", "markdown_content": "# A2\n\nBody"},
        post_id=post_a,
        action="draft",
    )
    # Post B now claims the freed "collide" slug.
    post_b = store.save_post(
        {"title": "B", "slug": "collide", "markdown_content": "# B\n\nBody"},
        action="draft",
    )
    assert store.get_post_by_id(post_b)["slug"] == "collide"

    # Oldest revision of A snapshots slug "collide"; restoring it must not collide with B.
    revisions = store.list_post_revisions(post_a)
    oldest = revisions[-1]
    restored = store.restore_post_revision(post_a, oldest["id"])

    assert restored["title"] == "A one"
    assert restored["status"] == "draft"
    assert restored["slug"] != store.get_post_by_id(post_b)["slug"]
    slugs = {store.get_post_by_id(post_a)["slug"], store.get_post_by_id(post_b)["slug"]}
    assert len(slugs) == 2


def test_publish_preflight_returns_errors_and_warnings(client):
    token = login(client)
    invalid = client.post(
        "/admin/api/validate-post",
        json={"fields": {"title": "", "markdown_content": ""}},
        headers={"X-CSRF-Token": token},
    )
    assert invalid.status_code == 400
    assert {item["code"] for item in invalid.get_json()["errors"]} >= {"title_required", "content_required"}

    valid = client.post(
        "/admin/api/validate-post",
        json={"fields": post_fields(markdown="# Short")},
        headers={"X-CSRF-Token": token},
    )
    assert valid.status_code == 200
    warning_codes = {item["code"] for item in valid.get_json()["warnings"]}
    assert "missing_sections" in warning_codes


def test_expired_trash_is_purged(app_bundle):
    _application, store = app_bundle
    post_id = store.save_post(post_fields(title="Expired"), action="draft")
    store.trash_post(post_id)
    with store.connect() as connection:
        connection.execute(
            "UPDATE posts SET deleted_at = ? WHERE id = ?",
            ("2020-01-01T00:00:00.000000", post_id),
        )
        connection.commit()
    assert store.purge_expired_trash(now=__import__("datetime").datetime(2026, 7, 21)) == 1
    assert store.get_post_by_id(post_id) is None


def test_media_library_reports_body_and_cover_references(app_bundle):
    _application, store = app_bundle
    relative = store.save_file(type("Upload", (), {"filename": "library.png", "mimetype": "image/png", "stream": image_bytes()})(), "media")
    url = "/uploads/" + relative
    store.save_post(
        {**post_fields(title="Media article"), "cover_image": url, "markdown_content": f"# Media\n\n## Section\n\n![image]({url})"},
        action="draft",
    )
    assets = store.list_media_assets()
    asset = next(item for item in assets if item["url"] == url)
    assert asset["reference_count"] == 2
    assert {item["kind"] for item in asset["references"]} == {"cover", "body"}


def test_admin_media_and_revision_surfaces_render(app_bundle, client):
    _application, store = app_bundle
    post_id = store.save_post(post_fields(title="Surface article"), action="draft")
    login(client)

    media_page = client.get("/admin/media")
    assert media_page.status_code == 200
    assert 'id="media-grid"' in media_page.get_data(as_text=True) or "还没有媒体文件" in media_page.get_data(as_text=True)

    write_page = client.get(f"/admin/write/{post_id}")
    assert write_page.status_code == 200
    html = write_page.get_data(as_text=True)
    assert 'id="revision-panel"' in html
    assert 'id="publish-warnings-acknowledged"' in html


# ---------------------------------------------------------------------------
# T1 — 上线校验报错消息必须包含中文（防 mojibake 复发）
# ---------------------------------------------------------------------------


def test_launch_config_messages_are_chinese(tmp_path, monkeypatch):
    """validate_launch_config 的每条 RuntimeError 必须含中文字符且不含乱码."""
    app_module = importlib.import_module("blog.app")

    # 6 类非法配置，每类对应一条 RuntimeError
    cases = [
        # (kwargs_overrides, expected_env_name_in_message)
        ({"secret_key": ""}, "BLOG_SECRET_KEY"),
        ({"secret_key": "a" * 100}, "BLOG_SECRET_KEY"),  # 默认值测试由另一个 case 覆盖
        ({"admin_password": "weak"}, "BLOG_ADMIN_PASSWORD"),
        ({"admin_prefix": "/admin"}, "BLOG_ADMIN_PREFIX"),
        ({"public_base_url": "", "require_public_base_url": True}, "BLOG_PUBLIC_BASE_URL"),
        ({"public_base_url": "http://example.com"}, "BLOG_PUBLIC_BASE_URL"),
    ]

    # 第一个 case 需要 secret_key != DEFAULT_SECRET_KEY 才会走 "过短" 分支
    # 其实 secret_key="" 走的是 not secret_key 分支
    # 第二个 "a"*100 不是默认值，不短——不触发。改为测试 cookie_secure：
    cases[1] = ({"public_base_url": "https://example.com", "cookie_secure": False}, "BLOG_COOKIE_SECURE")

    base = dict(
        debug_mode=False,
        secret_key="unique-test-secret-key-1234567890abcdef",
        admin_password="strong-enough-password",
        admin_prefix="/launch-admin",
        public_base_url="https://example.com",
        cookie_secure=True,
        require_public_base_url=False,
    )

    for overrides, env_name in cases:
        params = {**base, **overrides}
        try:
            app_module.validate_launch_config(**params)
        except RuntimeError as exc:
            msg = str(exc)
            assert re.search(r"[一-鿿]", msg), f"消息缺少中文字符: {msg}"
            assert "??" not in msg, f"消息含乱码: {msg}"
            assert env_name in msg, f"消息缺少变量名 {env_name}: {msg}"
        else:
            raise AssertionError(f"应抛出 RuntimeError: {overrides}")


# ---------------------------------------------------------------------------
# T2 — ops shell 脚本必须是 UTF-8 且无乱码
# ---------------------------------------------------------------------------


def test_ops_scripts_are_utf8_without_mojibake():
    """deploy/*.sh 必须是 UTF-8、含中文、无 ???? 乱码、无 BOM、无 CRLF."""
    repo_root = Path(__file__).resolve().parents[2]
    scripts = sorted((repo_root / "deploy").glob("*.sh"))
    assert scripts, "未找到任何 shell 脚本"

    for path in scripts:
        raw = path.read_bytes()
        # 无 BOM
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{path.name}: 含 UTF-8 BOM"
        # 无 CRLF
        assert b"\r\n" not in raw, f"{path.name}: 含 CRLF 换行"
        # UTF-8 严格可解码
        text = raw.decode("utf-8")
        # 含中文字符
        assert re.search(r"[一-鿿]", text), f"{path.name}: 缺少中文字符"
        # 无乱码（连续 ???? 不在 URL 查询字符串中）
        assert "????" not in text, f"{path.name}: 含乱码 ????"


# ---------------------------------------------------------------------------
# T3 — 默认（BLOG_TRUSTED_PROXY_COUNT=0）下伪造 XFF 无效
# ---------------------------------------------------------------------------


def test_login_rate_limit_ignores_forged_forwarded_for(client, app_bundle):
    """count=0 时完全忽略 XFF，不同伪造 IP 仍归入同一桶."""
    _application, _store = app_bundle
    token = csrf_token(client)
    for i in range(3):
        resp = client.post(
            "/admin/login",
            data={"password": "wrong", "csrf_token": token},
            headers={"X-Forwarded-For": f"10.0.0.{i + 1}"},
        )
        assert resp.status_code == 200
    resp = client.post(
        "/admin/login",
        data={"password": "wrong", "csrf_token": token},
        headers={"X-Forwarded-For": "10.0.0.99"},
    )
    assert resp.status_code == 429
    assert len(_application.extensions["blog_login_failures"]) == 1


# ---------------------------------------------------------------------------
# T4 — BLOG_TRUSTED_PROXY_COUNT=1 时取 XFF 链倒数第 1 段
# ---------------------------------------------------------------------------


def test_login_rate_limit_uses_trusted_proxy_chain(tmp_path, monkeypatch):
    """count=1 时取 XFF 链尾段；尾段相同归入同一桶，不同则分开."""
    monkeypatch.setenv("BLOG_TRUSTED_PROXY_COUNT", "1")
    monkeypatch.setenv("BLOG_DEBUG", "true")
    monkeypatch.setenv("BLOG_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/admin")
    monkeypatch.setenv("BLOG_DATABASE_PATH", str(tmp_path / "blog.db"))
    monkeypatch.setenv("BLOG_LOGIN_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("BLOG_LOGIN_RATE_WINDOW_SECONDS", "60")
    monkeypatch.delenv("BLOG_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "false")

    app_module = importlib.import_module("blog.app")
    store_module = importlib.import_module("blog.store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
    uploads_module = importlib.import_module("blog.uploads")
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(app_module, "UPLOADS_DIR", uploads_dir)

    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()

    # 取 CSRF token
    client.get("/admin/login")
    with client.session_transaction() as session:
        token = session["_admin_csrf_token"]

    # 尾段固定 203.0.113.7，前缀伪造变化 → 归入同一桶
    for i in range(3):
        resp = client.post(
            "/admin/login",
            data={"password": "wrong", "csrf_token": token},
            headers={"X-Forwarded-For": f"192.168.{i}.1, 203.0.113.7"},
        )
        assert resp.status_code == 200
    resp = client.post(
        "/admin/login",
        data={"password": "wrong", "csrf_token": token},
        headers={"X-Forwarded-For": "10.99.99.99, 203.0.113.7"},
    )
    assert resp.status_code == 429

    # 尾段不同 → 不同桶，应该可以正常登录
    resp = client.post(
        "/admin/login",
        data={"password": "wrong", "csrf_token": token},
        headers={"X-Forwarded-For": "192.168.1.1, 198.51.100.9"},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# T5 — 登录失败桶数量上限
# ---------------------------------------------------------------------------


def test_login_failure_buckets_are_capped(tmp_path, monkeypatch):
    """超过 LOGIN_FAILURE_MAX_KEYS 时淘汰最老的桶."""
    monkeypatch.setenv("BLOG_TRUSTED_PROXY_COUNT", "1")
    monkeypatch.setenv("BLOG_DEBUG", "true")
    monkeypatch.setenv("BLOG_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/admin")
    monkeypatch.setenv("BLOG_DATABASE_PATH", str(tmp_path / "blog.db"))
    monkeypatch.setenv("BLOG_LOGIN_MAX_ATTEMPTS", "10")
    monkeypatch.setenv("BLOG_LOGIN_RATE_WINDOW_SECONDS", "60")
    monkeypatch.delenv("BLOG_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "false")

    app_module = importlib.import_module("blog.app")
    store_module = importlib.import_module("blog.store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
    uploads_module = importlib.import_module("blog.uploads")
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(app_module, "UPLOADS_DIR", uploads_dir)

    monkeypatch.setattr(importlib.import_module("blog.security"), "LOGIN_FAILURE_MAX_KEYS", 4)
    monkeypatch.setattr(app_module, "LOGIN_FAILURE_MAX_KEYS", 4, raising=False)
    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()

    client.get("/admin/login")
    with client.session_transaction() as session:
        token = session["_admin_csrf_token"]

    # 10 个不同尾段各失败一次
    for i in range(10):
        client.post(
            "/admin/login",
            data={"password": "wrong", "csrf_token": token},
            headers={"X-Forwarded-For": f"10.0.0.1, 198.51.100.{i}"},
        )

    failures = application.extensions["blog_login_failures"]
    assert len(failures) <= 4


# ---------------------------------------------------------------------------
# T6 — passwords_match 处理非 ASCII 密码
# ---------------------------------------------------------------------------


def test_password_compare_handles_non_ascii():
    """passwords_match 必须能安全比较含中文的密码，不抛异常."""
    app_module = importlib.import_module("blog.app")

    assert app_module.passwords_match("密码密码密码", "密码密码密码") is True
    assert app_module.passwords_match("密码", "abc") is False
    assert app_module.passwords_match(None, "abc") is False
    assert app_module.passwords_match("", "") is True


# ---------------------------------------------------------------------------
# T7 — 非 ASCII 管理密码不会导致 500
# ---------------------------------------------------------------------------


def test_login_with_non_ascii_password_does_not_500(tmp_path, monkeypatch):
    """管理密码含中文时：错密码→200（非500）、可触发 429、对密码→302."""
    monkeypatch.setenv("BLOG_DEBUG", "true")
    monkeypatch.setenv("BLOG_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "正确密码正确密码正确密码")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/admin")
    monkeypatch.setenv("BLOG_DATABASE_PATH", str(tmp_path / "blog.db"))
    monkeypatch.setenv("BLOG_LOGIN_MAX_ATTEMPTS", "3")
    monkeypatch.setenv("BLOG_LOGIN_RATE_WINDOW_SECONDS", "60")
    monkeypatch.delenv("BLOG_PUBLIC_BASE_URL", raising=False)
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "false")

    app_module = importlib.import_module("blog.app")
    store_module = importlib.import_module("blog.store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
    uploads_module = importlib.import_module("blog.uploads")
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(app_module, "UPLOADS_DIR", uploads_dir)

    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()

    client.get("/admin/login")
    with client.session_transaction() as session:
        token = session["_admin_csrf_token"]

    # 错误密码 → 200（非 500）
    resp = client.post("/admin/login", data={"password": "错", "csrf_token": token})
    assert resp.status_code == 200

    # 连续错误后触发 429（证明失败被计数，未被 TypeError 跳过）
    client.post("/admin/login", data={"password": "错", "csrf_token": token})
    client.post("/admin/login", data={"password": "错", "csrf_token": token})
    resp = client.post("/admin/login", data={"password": "错", "csrf_token": token})
    assert resp.status_code == 429

    # 正确密码 → 302（后台首页）
    application.extensions["blog_login_failures"].clear()  # 重置限流
    client.get("/admin/login")  # 重新获取 session/token
    with client.session_transaction() as session:
        token = session["_admin_csrf_token"]
    resp = client.post(
        "/admin/login",
        data={"password": "正确密码正确密码正确密码", "csrf_token": token},
    )
    assert resp.status_code == 302


# ---------------------------------------------------------------------------
# T8 — safe_referrer_target 拒绝跨域 Referer
# ---------------------------------------------------------------------------


def test_safe_referrer_target_rejects_cross_origin():
    app_module = importlib.import_module("blog.app")

    admin_prefix = "/admin"
    host = "localhost"

    # 跨域 → None
    assert app_module.safe_referrer_target("https://evil.example/admin/x", admin_prefix, host) is None
    # 协议相对 → None
    assert app_module.safe_referrer_target("//evil.example/admin/x", admin_prefix, host) is None
    # javascript: → None
    assert app_module.safe_referrer_target("javascript:alert(1)", admin_prefix, host) is None
    # 非后台路径 → None
    assert app_module.safe_referrer_target("/other/path", admin_prefix, host) is None
    # 同源后台路径 → 原值
    assert app_module.safe_referrer_target("http://localhost/admin/write", admin_prefix, host) == "http://localhost/admin/write"
    # 无 Referer → None
    assert app_module.safe_referrer_target(None, admin_prefix, host) is None


# ---------------------------------------------------------------------------
# T9 — CSRF 失败不跟随外部 Referer
# ---------------------------------------------------------------------------


def test_csrf_failure_does_not_follow_external_referer(client):
    """无 CSRF token 的 POST 带恶意 Referer → 302 不含 evil 域."""
    resp = client.post(
        "/admin/profile",
        data={"name": "x"},
        headers={"Referer": "https://evil.example/phish"},
    )
    assert resp.status_code == 302
    assert "evil.example" not in (resp.location or "")
    assert "/admin/login" in (resp.location or "")

    # 同源 Referer → 保留
    resp = client.post(
        "/admin/profile",
        data={"name": "x"},
        headers={"Referer": "http://localhost/admin/write"},
    )
    assert resp.status_code == 302
    assert resp.location.endswith("/admin/write")


# ---------------------------------------------------------------------------
# T10 — HSTS 仅在 BLOG_COOKIE_SECURE=true 时下发
# ---------------------------------------------------------------------------


def test_hsts_header_follows_cookie_secure(client):
    """默认 BLOG_COOKIE_SECURE=false → 无 HSTS；true 时应下发."""
    resp = client.get("/api/health")
    assert "Strict-Transport-Security" not in resp.headers


def test_hsts_header_present_when_secure(tmp_path, monkeypatch):
    monkeypatch.setenv("BLOG_DEBUG", "true")
    monkeypatch.setenv("BLOG_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/admin")
    monkeypatch.setenv("BLOG_DATABASE_PATH", str(tmp_path / "blog.db"))
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "true")
    monkeypatch.delenv("BLOG_PUBLIC_BASE_URL", raising=False)

    app_module = importlib.import_module("blog.app")
    store_module = importlib.import_module("blog.store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
    uploads_module = importlib.import_module("blog.uploads")
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(app_module, "UPLOADS_DIR", uploads_dir)

    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()
    resp = client.get("/api/health")
    hsts = resp.headers.get("Strict-Transport-Security", "")
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts


# ---------------------------------------------------------------------------
# T11 — 弱 SECRET_KEY（含过短）被拒绝
# ---------------------------------------------------------------------------


def test_short_secret_key_is_rejected():
    app_module = importlib.import_module("blog.app")

    base = dict(
        debug_mode=False,
        admin_password="strong-enough-password",
        admin_prefix="/launch-admin",
        public_base_url="https://example.com",
        cookie_secure=True,
    )
    # 31 字符 → 拒绝
    with pytest.raises(RuntimeError, match="BLOG_SECRET_KEY"):
        app_module.validate_launch_config(secret_key="a" * 31, **base)
    # 32 字符 → 通过
    app_module.validate_launch_config(secret_key="a" * 32, **base)
    # 已知弱密钥 → 拒绝
    with pytest.raises(RuntimeError, match="BLOG_SECRET_KEY"):
        app_module.validate_launch_config(secret_key="replace-with-a-random-secret", **base)


# ---------------------------------------------------------------------------
# T12 — feed.xml 属性内引号被正确转义
# ---------------------------------------------------------------------------


def test_feed_link_attributes_escape_quotes(tmp_path, monkeypatch):
    """BLOG_PUBLIC_BASE_URL 含引号时，feed.xml 属性内应出现 &quot;."""
    monkeypatch.setenv("BLOG_DEBUG", "true")
    monkeypatch.setenv("BLOG_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/admin")
    monkeypatch.setenv("BLOG_DATABASE_PATH", str(tmp_path / "blog.db"))
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "false")
    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", 'https://example.com/a"b')

    app_module = importlib.import_module("blog.app")
    store_module = importlib.import_module("blog.store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
    uploads_module = importlib.import_module("blog.uploads")
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(app_module, "UPLOADS_DIR", uploads_dir)

    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()
    resp = client.get("/feed.xml")
    body = resp.get_data(as_text=True)
    # 不应出现裸引号在 href= 里
    assert 'href="https://example.com/a"b' not in body
    # 应出现转义后的 &quot;
    assert "&quot;" in body


# ---------------------------------------------------------------------------
# T13 — 审计日志记录登录事件且不含明文密码
# ---------------------------------------------------------------------------


def test_audit_log_records_login_events(client, caplog):
    """登录失败/成功均应写入审计日志，且不含密码明文."""
    import logging as _logging

    caplog.set_level(_logging.INFO, logger="flask.app")

    token = csrf_token(client)

    # 失败登录
    with caplog.at_level(_logging.INFO, logger="flask.app"):
        client.post("/admin/login", data={"password": "wrong-password", "csrf_token": token})
    assert "audit login.failed" in caplog.text
    assert "wrong-password" not in caplog.text

    caplog.clear()

    # 成功登录
    with caplog.at_level(_logging.INFO, logger="flask.app"):
        client.post("/admin/login", data={"password": "test-password", "csrf_token": token})
    assert "audit login.success" in caplog.text
    assert "test-password" not in caplog.text


def test_published_autosave_updates_post_in_place(app_bundle, client):
    _application, store = app_bundle
    post_id = store.save_post(post_fields(title="Live title", slug="live-title", markdown="# Live\n\n## Section\n\nPublic body"), action="published")
    live = store.get_post_by_id(post_id)
    token = login(client)

    response = client.post(
        "/admin/api/autosave",
        json={
            "post_id": post_id,
            "updated_at": live["updated_at"],
            "fields": post_fields(title="Updated title", slug="live-title", markdown="# Updated\n\n## Section\n\nPublic body"),
        },
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["edit_source"] == "post"
    assert payload["status"] == "published"
    assert "pending_changes" not in payload
    assert store.get_post_by_id(post_id)["title"] == "Updated title"
    assert client.get("/api/posts/live-title").get_json()["title"] == "Updated title"

    stale = client.post(
        "/admin/api/autosave",
        json={
            "post_id": post_id,
            "updated_at": live["updated_at"],
            "fields": post_fields(title="Stale edit", slug="live-title"),
        },
        headers={"X-CSRF-Token": token},
    )
    assert stale.status_code == 409


def test_publish_update_preserves_pre_publish_revision(app_bundle, client):
    _application, store = app_bundle
    post_id = store.save_post(post_fields(title="Live copy"), action="published")
    token = login(client)
    fields = post_fields(title="Updated copy", markdown="# Updated\n\n## Section\n\nLong enough content")

    publish = client.post(
        "/admin/posts/save",
        data={"csrf_token": token, "post_id": post_id, **fields, "action": "published"},
    )
    assert publish.status_code == 302
    assert store.get_post_by_id(post_id)["title"] == "Updated copy"
    assert store.get_post_by_id(post_id)["status"] == "published"
    revision_types = [item["revision_type"] for item in store.list_post_revisions(post_id)]
    assert revision_types[:2] == ["published", "pre_publish"]

    with pytest.raises(PostVersionConflict):
        store.save_post(
            post_fields(title="Stale"),
            post_id=post_id,
            action="update",
            expected_updated_at="1999-01-01T00:00:00",
        )


def test_untitled_autosave_and_revision_restore_updates_post_directly(app_bundle, client):
    _application, store = app_bundle
    token = login(client)
    untitled = client.post(
        "/admin/api/autosave",
        json={"fields": {"title": "", "slug": "", "markdown_content": "an idea"}},
        headers={"X-CSRF-Token": token},
    )
    assert untitled.status_code == 200
    untitled_post = store.get_post_by_id(untitled.get_json()["id"])
    assert untitled_post["title"] == ""
    assert untitled_post["slug"].startswith("draft-")

    post_id = store.save_post(post_fields(title="Version one"), action="published")
    store.save_post(post_fields(title="Version two"), post_id=post_id, action="published")
    old_revision = store.list_post_revisions(post_id)[-1]
    restored = store.restore_post_revision(post_id, old_revision["id"])
    assert restored["status"] == "published"
    assert restored["title"] == "Version one"
    assert store.get_post_by_id(post_id)["title"] == "Version one"
    assert [item["revision_type"] for item in store.list_post_revisions(post_id)[:2]] == ["restored", "pre_restore"]


def test_media_references_preview_and_dashboard_author_surfaces(app_bundle, client):
    _application, store = app_bundle
    relative = store.save_file(type("Upload", (), {"filename": "surface.png", "mimetype": "image/png", "stream": image_bytes()})(), "media")
    url = "/uploads/" + relative
    post_id = store.save_post(
        {**post_fields(title="Surface live"), "cover_image": url, "markdown_content": f"# Surface\n\n## Section\n\n![alt]({url})"},
        action="published",
    )
    asset = next(item for item in store.list_media_assets() if item["url"] == url)
    assert {item["kind"] for item in asset["references"]} >= {"cover", "body"}

    token = login(client)
    assert client.get(f"/admin/api/posts/{post_id}/diff").status_code == 404
    assert client.delete(f"/admin/api/posts/{post_id}/working-copy", headers={"X-CSRF-Token": token}).status_code in (404, 405)
    assert client.get(f"/admin/preview/{post_id}").status_code == 200
    # 后台预览不得调用 highlightElement 让 hljs 自动猜语言：目录树/YAML/表格
    # 会被猜成 python/sql/bash 并染上错误配色。必须走 highlightDeclared 包装。
    preview_html = client.get(f"/admin/preview/{post_id}").get_data(as_text=True)
    assert "js/highlight.js" in preview_html
    assert "highlightElement" not in preview_html
    assert client.get("/admin/api/media").status_code == 200
    dashboard = client.get("/admin").get_data(as_text=True)
    assert "继续上次的工作" in dashboard
    assert "已发布文章的修改保存后直接生效。" in dashboard


def test_temporary_slug_promotes_and_unpublish_trash_keep_post_content(app_bundle):
    _application, store = app_bundle
    post_id = store.save_post({"title": "", "slug": "", "markdown_content": "idea"}, action="draft", allow_untitled=True)
    assert store.get_post_by_id(post_id)["slug"].startswith("draft-")
    store.save_post({"title": "Named draft", "slug": "", "markdown_content": "idea"}, post_id=post_id, action="draft", create_revision=False)
    assert store.get_post_by_id(post_id)["slug"] == "named-draft"

    published_id = store.save_post(post_fields(title="Online base", slug="online-base"), action="published")
    unpublished = store.unpublish_post(published_id)
    assert unpublished["status"] == "draft"
    assert unpublished["title"] == "Online base"
    assert [item["revision_type"] for item in store.list_post_revisions(published_id)[:2]] == ["unpublished", "pre_unpublish"]

    republished_id = store.save_post(post_fields(title="Trash live", slug="trash-live"), action="published")
    store.trash_post(republished_id)
    trashed = store.get_post_by_id(republished_id)
    assert trashed["status"] == "trashed"
    assert trashed["title"] == "Trash live"
    assert [item["revision_type"] for item in store.list_post_revisions(republished_id)[:2]] == ["trashed", "pre_trash"]


def test_media_original_filename_publish_image_checks_and_health(app_bundle):
    _application, store = app_bundle
    upload = type("Upload", (), {"filename": "meaningful-name.png", "mimetype": "image/png", "stream": image_bytes()})()
    payload = store.upload_media(upload)
    assert payload["original_filename"] == "meaningful-name.png"
    asset = next(item for item in store.list_media_assets() if item["url"] == payload["url"])
    assert asset["original_filename"] == "meaningful-name.png"

    validation = store.validate_post_for_publish(
        post_fields(
            title="Images",
            slug="images",
            markdown=f"# Images\n\n## Section\n\n![image]({payload['url']})\n\n![](/uploads/media/missing.png)",
        )
    )
    assert {item["code"] for item in validation["warnings"]} >= {"missing_image_alt"}
    assert {item["code"] for item in validation["errors"]} >= {"missing_local_image"}

    store.save_post(post_fields(title="No section", slug="no-section", markdown="# Only title\n\nText"), action="draft")
    health = store.content_health()
    assert health["missing_sections"] >= 1
    assert health["empty_image_alt"] >= 0


def test_author_attention_and_admin_ui_surfaces(app_bundle, client):
    _application, store = app_bundle
    post_id = store.save_post(post_fields(title="Draft one", slug="draft-one"), action="draft")
    store.save_post(post_fields(title="Draft two", slug="draft-one", markdown="# Two\n\n## Section\n\nChanged"), post_id=post_id, action="draft")
    assert store.list_post_revisions(post_id)
    assert store.author_attention_items() is not None

    login(client)
    write_html = client.get(f"/admin/write/{post_id}").get_data(as_text=True)
    assert 'id="diff-left"' not in write_html
    assert 'id="diff-right"' not in write_html
    assert 'id="tag-suggestions"' in write_html
    assert 'id="generate-slug-button"' in write_html
    profile_html = client.get("/admin/profile").get_data(as_text=True)
    assert 'id="profile-preview-home"' in profile_html
    assert 'id="profile-preview-about"' in profile_html
    assert "avatar" not in profile_html
    assert 'name="role"' not in profile_html
    assert 'name="location"' not in profile_html
    assert 'name="hero_note"' not in profile_html
    assert 'name="update_calendar"' not in profile_html


def test_schema_migrations_are_idempotent(app_bundle):
    _application, store = app_bundle
    store.init()
    store.init()
    with store.connect() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        post_columns = {row["name"] for row in connection.execute("PRAGMA table_info(posts)").fetchall()}
        profile_columns = {row["name"] for row in connection.execute("PRAGMA table_info(site_profile)").fetchall()}
    assert "media_metadata" in tables
    assert "post_working_copies" not in tables
    assert {"featured", "tone", "locale", "translation_of"}.isdisjoint(post_columns)
    assert {"role", "location", "hero_note", "update_calendar", "avatar_path"}.isdisjoint(profile_columns)


def test_legacy_schema_is_cleaned_up_on_migration(app_bundle):
    _application, store = app_bundle
    post_id = store.save_post(
        {"title": "Migrate Me", "slug": "migrate-me", "markdown_content": "body"},
        action="draft",
    )
    with store.connect() as connection:
        connection.execute("ALTER TABLE posts ADD COLUMN featured INTEGER NOT NULL DEFAULT 0")
        connection.execute("ALTER TABLE posts ADD COLUMN tone TEXT DEFAULT 'amber'")
        connection.execute("ALTER TABLE posts ADD COLUMN locale TEXT DEFAULT ''")
        connection.execute("ALTER TABLE posts ADD COLUMN translation_of INTEGER")
        connection.execute("ALTER TABLE site_profile ADD COLUMN role TEXT DEFAULT ''")
        connection.execute("ALTER TABLE site_profile ADD COLUMN location TEXT DEFAULT ''")
        connection.execute("ALTER TABLE site_profile ADD COLUMN hero_note TEXT DEFAULT ''")
        connection.execute("ALTER TABLE site_profile ADD COLUMN update_calendar TEXT NOT NULL DEFAULT '[]'")
        connection.execute("ALTER TABLE site_profile ADD COLUMN avatar_path TEXT DEFAULT ''")
        connection.execute("CREATE TABLE post_working_copies (post_id INTEGER PRIMARY KEY)")
        connection.execute(
            "INSERT INTO post_revisions (post_id, revision_type, snapshot_json, created_at) "
            "VALUES (?, 'discarded_changes', '{}', '2026-01-01T00:00:00')",
            (post_id,),
        )
        connection.commit()

    store.init()

    with store.connect() as connection:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        post_columns = {row["name"] for row in connection.execute("PRAGMA table_info(posts)").fetchall()}
        profile_columns = {row["name"] for row in connection.execute("PRAGMA table_info(site_profile)").fetchall()}
        legacy_revisions = connection.execute(
            "SELECT COUNT(*) FROM post_revisions WHERE revision_type IN ('discarded_changes', 'restored_to_working_copy')"
        ).fetchone()[0]
    assert "post_working_copies" not in tables
    assert {"featured", "tone", "locale", "translation_of"}.isdisjoint(post_columns)
    assert {"role", "location", "hero_note", "update_calendar", "avatar_path"}.isdisjoint(profile_columns)
    assert legacy_revisions == 0
    # Cleaned-up database must still serve posts normally.
    assert store.get_post_by_id(post_id) is not None


def test_quick_publish_validates_and_publishes(app_bundle, client):
    _application, store = app_bundle
    token = login(client)
    post_id = store.save_post(
        {
            "title": "Quick Post",
            "slug": "quick-post",
            "markdown_content": "## Section\n\nEnough body text to pass checks.",
            "excerpt": "An excerpt.",
        },
        action="draft",
    )
    response = client.post(f"/admin/posts/{post_id}/quick-publish", data={"csrf_token": token})
    assert response.status_code == 302
    assert response.location.endswith("/admin")
    assert store.get_post_by_id(post_id)["status"] == "published"
    assert client.get("/api/posts/quick-post").status_code == 200

    # Draft missing required content must be rejected and routed to the editor.
    bad_id = store.save_post(
        {"title": "No Body", "slug": "no-body", "markdown_content": ""},
        action="draft",
    )
    response = client.post(f"/admin/posts/{bad_id}/quick-publish", data={"csrf_token": token})
    assert response.status_code == 302
    assert f"/admin/write/{bad_id}" in response.location
    assert store.get_post_by_id(bad_id)["status"] == "draft"


def test_bulk_post_actions(app_bundle, client):
    _application, store = app_bundle
    token = login(client)
    ids = [
        store.save_post(
            {"title": f"Bulk {i}", "slug": f"bulk-{i}", "markdown_content": "body"},
            action="draft",
        )
        for i in range(3)
    ]

    response = client.post(
        "/admin/posts/bulk",
        data={"csrf_token": token, "action": "trash", "post_ids": [str(item) for item in ids]},
    )
    assert response.status_code == 302
    assert all(store.get_post_by_id(item)["status"] == "trashed" for item in ids)

    client.post("/admin/posts/bulk", data={"csrf_token": token, "action": "restore", "post_ids": [str(ids[0])]})
    assert store.get_post_by_id(ids[0])["status"] == "draft"

    client.post("/admin/posts/bulk", data={"csrf_token": token, "action": "purge", "post_ids": [str(ids[1])]})
    assert store.get_post_by_id(ids[1]) is None

    # Purging a non-trashed post fails without affecting it.
    client.post("/admin/posts/bulk", data={"csrf_token": token, "action": "purge", "post_ids": [str(ids[0])]})
    assert store.get_post_by_id(ids[0]) is not None

    # Unknown actions and empty selections are rejected gracefully.
    assert client.post("/admin/posts/bulk", data={"csrf_token": token, "action": "explode", "post_ids": [str(ids[0])]}).status_code == 302
    assert client.post("/admin/posts/bulk", data={"csrf_token": token, "action": "trash"}).status_code == 302
    assert store.get_post_by_id(ids[0])["status"] == "draft"


def test_dashboard_chrome_includes_bulk_sort_and_help(app_bundle, client):
    _application, store = app_bundle
    store.save_post(
        {"title": "Bulk Chrome", "slug": "bulk-chrome", "markdown_content": "body"},
        action="draft",
    )
    login(client)
    html = client.get("/admin").get_data(as_text=True)
    assert 'id="bulk-form"' in html
    assert 'id="admin-post-sort"' in html
    assert 'id="admin-help-dialog"' in html
    assert 'id="help-toggle"' in html
    for marker in ('data-bulk="trash"', 'data-bulk="restore"', 'data-bulk="purge"'):
        assert marker in html


def test_legacy_excerpts_are_regenerated_on_migration(app_bundle):
    _application, store = app_bundle
    post_id = store.save_post(
        {"title": "Excerpt Fix", "slug": "excerpt-fix", "markdown_content": "body"},
        action="draft",
    )
    with store.connect() as connection:
        connection.execute(
            "UPDATE posts SET excerpt = ?, markdown_content = ? WHERE id = ?",
            ("Intro ![462](old-image.png) body", "## Section\n\nIntro text body here.", post_id),
        )
        connection.commit()

    store.init()

    assert "![" not in store.get_post_by_id(post_id)["excerpt"]


def test_admin_static_assets_are_not_cached(client):
    login(client)
    response = client.get("/static/admin/css/base.css")
    assert response.status_code == 200
    assert "no-cache" in (response.headers.get("Cache-Control") or "")