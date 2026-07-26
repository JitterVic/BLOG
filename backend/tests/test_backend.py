import io
import importlib
import re
import sys
import time
from pathlib import Path

import pytest
from PIL import Image


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

    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    app_module = importlib.import_module("app")
    store_module = importlib.import_module("store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
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
    assert response.get_json() == []
    assert client.get("/api/posts/hidden-draft").status_code == 404


def test_markdown_sanitizes_dangerous_links_and_tags(app_bundle):
    _application, store = app_bundle
    html = importlib.import_module("store").render_markdown(
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
    assert response.get_json()["html"] == "<h1>hi</h1>"


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


def test_search_tags_and_pagination(client):
    response = client.get("/api/posts?q=Flask&page=1&limit=1")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["page"] == 1
    assert payload["per_page"] == 1
    assert payload["total"] >= 1
    assert len(payload["items"]) == 1
    assert "Flask" in payload["items"][0]["tags"]


def test_admin_phase_two_pages_render_accessible_controls(client):
    login(client)
    dashboard = client.get("/admin").get_data(as_text=True)
    assert "dashboard-overview" in dashboard
    assert "dashboard-stat" in dashboard
    assert "data-confirm-form" in dashboard
    assert 'aria-live="polite"' in dashboard

    profile = client.get("/admin/profile").get_data(as_text=True)
    assert 'id="profile-form"' in profile
    assert 'id="avatar-preview"' in profile
    assert "field-help" in profile
    assert "data-loading-form" in profile


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
    template = Path("backend/templates/admin_write.html").read_text(encoding="utf-8")
    script = Path("backend/static/admin/admin-write.js").read_text(encoding="utf-8")
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
    unique_category = "PhaseFiveRelCat"
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
            "category": "OtherCat",
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

    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    app_module = importlib.import_module("app")

    monkeypatch.setenv("BLOG_SECRET_KEY", "dev-secret-key-change-me")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "strong-enough-password")
    monkeypatch.setenv("BLOG_ADMIN_PREFIX", "/launch-admin")
    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", "https://example.com")
    monkeypatch.setenv("BLOG_COOKIE_SECURE", "true")
    with pytest.raises(RuntimeError, match="BLOG_SECRET_KEY"):
        app_module.create_app()

    monkeypatch.setenv("BLOG_SECRET_KEY", "unique-test-secret-1234567890")
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
    uploads = Path(importlib.import_module("store").UPLOADS_DIR)
    media = uploads / "media"
    media.mkdir(parents=True, exist_ok=True)
    target = media / "evil.svg"
    target.write_text("<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", encoding="utf-8")
    response = client.get("/uploads/media/evil.svg")
    assert response.status_code == 404


def test_env_int_falls_back_on_invalid_values(monkeypatch):
    env_loader = importlib.import_module("env_loader")
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
    item = next(entry for entry in payload if entry["slug"] == "compact-list-body")
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
    script = Path("backend/static/admin/admin.js").read_text(encoding="utf-8")
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
    assert "published-autosave-tip" in page
    assert "write-status-bar" in page


def test_css_contains_no_toc_rule():
    admin_css = Path("backend/static/admin/admin.css").read_text(encoding="utf-8")
    front_css = Path("frontend/src/styles/editorial.css").read_text(encoding="utf-8")
    assert "write-status-badge" in admin_css
    assert ("post-reading-layout--no-toc" in front_css) or ("--no-toc" in front_css) or ("post-reading-layout--no-toc" in admin_css)


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
    import app as app_module

    monkeypatch.setattr(app_module, "FRONTEND_DIST", dist)
    monkeypatch.setenv("BLOG_PUBLIC_BASE_URL", "https://example.com")
    # recreate app with patched FRONTEND_DIST
    application = app_module.create_app()
    application.config.update(TESTING=True)
    client = application.test_client()
    store = app_module.BlogStore if False else store
    # store still points to tmp db from fixture; need same store path
    from store import BlogStore
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
    from store import UPLOADS_DIR

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
        "category": "Testing",
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
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    app_module = importlib.import_module("app")

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
    """deploy.sh 和 deploy/*.sh 必须是 UTF-8、含中文、无 ???? 乱码、无 BOM、无 CRLF."""
    repo_root = Path(__file__).resolve().parents[2]
    scripts = [repo_root / "deploy.sh"]
    scripts.extend(sorted((repo_root / "deploy").glob("*.sh")))
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

    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    app_module = importlib.import_module("app")
    store_module = importlib.import_module("store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
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

    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    app_module = importlib.import_module("app")
    store_module = importlib.import_module("store")
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(app_module, "UPLOADS_DIR", uploads_dir)

    monkeypatch.setattr(app_module, "LOGIN_FAILURE_MAX_KEYS", 4)
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
