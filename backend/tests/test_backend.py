import io
import importlib
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
    monkeypatch.setenv("BLOG_SECRET_KEY", "dev-secret-key-change-me")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "strong-enough-password")
    monkeypatch.setenv("BLOG_DATABASE_PATH", str(tmp_path / "blog.db"))

    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    app_module = importlib.import_module("app")

    with pytest.raises(RuntimeError, match="BLOG_SECRET_KEY"):
        app_module.create_app()

    monkeypatch.setenv("BLOG_SECRET_KEY", "unique-test-secret")
    monkeypatch.setenv("BLOG_ADMIN_PASSWORD", "admin123456")
    with pytest.raises(RuntimeError, match="BLOG_ADMIN_PASSWORD"):
        app_module.create_app()


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

