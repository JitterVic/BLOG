"""共享测试装置：应用工厂、测试客户端与登录辅助。

``test_backend.py`` 保留了自己的同名装置（局部定义优先级更高），此处主要服务
新增的测试模块，避免各文件重复搭建环境。
"""

import importlib

import pytest


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
    monkeypatch.setattr(store_module, "UPLOADS_DIR", uploads_dir, raising=False)
    uploads_module = importlib.import_module("blog.uploads")
    monkeypatch.setattr(uploads_module, "UPLOADS_DIR", uploads_dir)
    monkeypatch.setattr(app_module, "UPLOADS_DIR", uploads_dir, raising=False)

    application = app_module.create_app()
    application.config.update(TESTING=True)
    return application, store_module.BlogStore(tmp_path / "blog.db")


@pytest.fixture()
def client(app_bundle):
    application, _store = app_bundle
    return application.test_client()


def csrf_token(test_client):
    test_client.get("/admin/login")
    with test_client.session_transaction() as session:
        return session["_admin_csrf_token"]


def login(test_client):
    token = csrf_token(test_client)
    response = test_client.post(
        "/admin/login", data={"password": "test-password", "csrf_token": token}
    )
    assert response.status_code == 302
    with test_client.session_transaction() as session:
        return session["_admin_csrf_token"]
