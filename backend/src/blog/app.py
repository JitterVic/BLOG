"""应用工厂：组装配置、安全钩子、存储与各路由蓝图。"""

import logging

from flask import Flask, flash, redirect, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from .config import (  # noqa: F401  (兼容重导出)
    DEFAULT_ADMIN_PASSWORD,
    DEFAULT_SECRET_KEY,
    validate_launch_config,
)
from .config import load_launch_settings
from .env_loader import load_env_file, project_root
from .routes import register_routes
from .routes.spa import FRONTEND_DIST  # noqa: F401  (兼容重导出)
from .security import LOGIN_FAILURE_MAX_KEYS  # noqa: F401  (兼容重导出)
from .security import AdminSecurity, api_error, passwords_match, safe_referrer_target  # noqa: F401
from .store import BlogStore
from .uploads import UPLOADS_DIR  # noqa: F401  (兼容重导出)

ROOT_DIR = project_root()
load_env_file(ROOT_DIR / ".env")


def create_app():
    app = Flask(__name__)
    app.logger.setLevel(logging.INFO)
    settings = load_launch_settings()

    app.secret_key = settings.secret_key
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.cookie_secure,
        SESSION_PERMANENT=True,
        PERMANENT_SESSION_LIFETIME=settings.session_lifetime,
        SESSION_REFRESH_EACH_REQUEST=True,
        MAX_CONTENT_LENGTH=settings.max_upload_bytes,
        BLOG_DEBUG=settings.debug_mode,
        BLOG_ADMIN_PASSWORD=settings.admin_password,
        BLOG_REQUIRE_PUBLIC_BASE_URL=settings.require_public_base_url,
        ADMIN_PREFIX=settings.admin_prefix,
    )

    store = BlogStore()
    store.init()
    store.purge_expired_trash(retention_days=30)

    security = AdminSecurity(app, settings)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(error):
        if security.is_admin_api_request() or request.is_json:
            return api_error("payload_too_large", "上传内容过大，请压缩文件后重试。", 413)
        flash("上传内容过大，请压缩文件后重试。", "error")
        fallback = url_for("admin_dashboard") if security.is_authenticated() else url_for("admin_login")
        return redirect(
            safe_referrer_target(request.referrer, settings.admin_prefix, request.host) or fallback
        )

    @app.errorhandler(404)
    def handle_not_found(error):
        if request.path.startswith("/api/") or security.is_admin_api_request():
            return api_error("not_found", "请求的内容不存在。", 404)
        return error

    @app.errorhandler(500)
    def handle_server_error(error):
        if request.path.startswith("/api/") or security.is_admin_api_request():
            return api_error("server_error", "服务暂时不可用，请稍后重试。", 500)
        return error

    register_routes(app, store=store, security=security, settings=settings)
    return app


app = create_app()
