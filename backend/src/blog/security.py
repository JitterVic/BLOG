"""管理后台安全层：会话鉴权、CSRF、登录限流、安全响应头与审计日志。"""

from __future__ import annotations

import logging
import secrets
import time
from functools import wraps
from urllib.parse import urlsplit

from flask import flash, jsonify, redirect, request, session, url_for

from .config import DEFAULT_ADMIN_PASSWORD, LaunchSettings
from .login_throttle import LoginFailureStore

LOGIN_FAILURE_MAX_KEYS = 2048
CSRF_SESSION_KEY = "_admin_csrf_token"


def api_error(code: str, error: str, status: int):
    """统一的 JSON 错误响应。"""
    return jsonify({"ok": False, "code": code, "error": error}), status


def is_safe_admin_next(target: str | None, admin_prefix: str) -> bool:
    if not target:
        return False
    parsed = urlsplit(target)
    return (
        not parsed.scheme
        and not parsed.netloc
        and parsed.path.startswith(f"{admin_prefix}/")
    )


def passwords_match(candidate: str | None, expected: str | None) -> bool:
    """Constant-time comparison that handles non-ASCII passwords safely."""
    try:
        return secrets.compare_digest(
            str(candidate or "").encode("utf-8"),
            str(expected or "").encode("utf-8"),
        )
    except (UnicodeEncodeError, TypeError):
        return False


def safe_referrer_target(referrer: str | None, admin_prefix: str, host: str) -> str | None:
    """Return *referrer* only when it points back to our own admin area."""
    if not referrer:
        return None
    parsed = urlsplit(referrer)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return None
    if parsed.netloc and parsed.netloc != host:
        return None
    path = parsed.path or ""
    if path != admin_prefix and not path.startswith(f"{admin_prefix}/"):
        return None
    return referrer


class AdminSecurity:
    """聚合鉴权相关钩子与工具，随应用实例创建。"""

    def __init__(self, app, settings: LaunchSettings, *, db=None):
        self.app = app
        self.settings = settings
        self.admin_prefix = settings.admin_prefix
        # Shared across workers and restart-durable when a database is supplied;
        # falls back to a plain dict for unit tests that construct the security
        # layer standalone.
        if db is not None:
            self.login_failures = LoginFailureStore(
                db,
                window_seconds=settings.login_window_seconds,
                max_keys=LOGIN_FAILURE_MAX_KEYS,
            )
        else:
            self.login_failures = {}
        app.extensions["blog_login_failures"] = self.login_failures

        @app.context_processor
        def inject_admin_security_context():
            return {"csrf_token": self.csrf_token}

        app.before_request(self.protect_admin_mutations)
        app.after_request(self.apply_security_headers)

    # ------------------------------------------------------------------
    # 基础判断
    # ------------------------------------------------------------------

    def is_authenticated(self) -> bool:
        return session.get("admin_authenticated") is True

    def is_admin_api_request(self) -> bool:
        return request.path.startswith(f"{self.admin_prefix}/api/")

    # ------------------------------------------------------------------
    # CSRF
    # ------------------------------------------------------------------

    def csrf_token(self) -> str:
        token = session.get(CSRF_SESSION_KEY)
        if not token:
            token = secrets.token_urlsafe(32)
            session[CSRF_SESSION_KEY] = token
        return token

    def valid_csrf_token(self, candidate: str | None) -> bool:
        expected = session.get(CSRF_SESSION_KEY)
        return bool(expected and candidate and secrets.compare_digest(str(candidate), str(expected)))

    # ------------------------------------------------------------------
    # 客户端识别与审计
    # ------------------------------------------------------------------

    def client_key(self) -> str:
        remote = (request.remote_addr or "").strip() or "unknown"
        trusted_proxy_count = self.settings.trusted_proxy_count
        if trusted_proxy_count <= 0:
            return remote
        chain = [item.strip() for item in (request.headers.get("X-Forwarded-For") or "").split(",") if item.strip()]
        if not chain:
            return remote
        index = max(0, len(chain) - trusted_proxy_count)
        return chain[index] or remote

    def audit(self, event: str, *, level: int = logging.INFO, **fields) -> None:
        detail = " ".join(f"{key}={value}" for key, value in fields.items() if value not in (None, ""))
        self.app.logger.log(level, "audit %s client=%s %s", event, self.client_key(), detail)

    # ------------------------------------------------------------------
    # 登录限流
    # ------------------------------------------------------------------

    def prune_login_failures(self, now: float) -> None:
        window = self.settings.login_window_seconds
        for key in [k for k, stamps in list(self.login_failures.items())
                    if not stamps or now - stamps[-1] >= window]:
            self.login_failures.pop(key, None)
        # 上限值允许测试通过模块属性动态调整。
        from . import security as security_module

        overflow = len(self.login_failures) - security_module.LOGIN_FAILURE_MAX_KEYS
        if overflow > 0:
            for key, _ in sorted(list(self.login_failures.items()), key=lambda item: item[1][-1])[:overflow]:
                self.login_failures.pop(key, None)

    def login_rate_limited(self) -> tuple[bool, int]:
        # Wall clock, not monotonic: timestamps are shared between workers and
        # persist across restarts, so they must mean the same thing everywhere.
        now = time.time()
        key = self.client_key()
        window = self.settings.login_window_seconds
        max_attempts = self.settings.login_max_attempts
        self.prune_login_failures(now)
        attempts = [stamp for stamp in self.login_failures.get(key, []) or [] if now - stamp < window]
        if not attempts:
            self.login_failures.pop(key, None)
            return False, 0
        if len(attempts) < max_attempts:
            return False, 0
        retry_after = max(1, int(window - (now - attempts[0])))
        return True, retry_after

    def register_login_failure(self) -> None:
        now = time.time()
        key = self.client_key()
        store = self.login_failures
        if isinstance(store, LoginFailureStore):
            store.record_failure(key, now=now)
            return
        window = self.settings.login_window_seconds
        max_attempts = self.settings.login_max_attempts
        attempts = [stamp for stamp in store.get(key, []) or [] if now - stamp < window]
        attempts.append(now)
        store[key] = attempts[-max_attempts:]
        self.prune_login_failures(now)

    # ------------------------------------------------------------------
    # 请求钩子
    # ------------------------------------------------------------------

    def protect_admin_mutations(self):
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if not (request.path == self.admin_prefix or request.path.startswith(f"{self.admin_prefix}/")):
            return None
        if self.is_admin_api_request() and not self.is_authenticated():
            return api_error("auth_required", "登录状态已失效，请重新登录。", 401)
        candidate = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if self.valid_csrf_token(candidate):
            return None
        if self.is_admin_api_request() or request.is_json:
            return api_error("csrf_failed", "请求校验已失效，请刷新页面后重试。", 400)
        self.audit("csrf.failed", level=logging.WARNING, path=request.path)
        flash("请求校验已失效，请刷新页面后重试。", "error")
        return redirect(safe_referrer_target(request.referrer, self.admin_prefix, request.host) or url_for("admin_login"))

    def apply_security_headers(self, response):
        settings = self.settings
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.path.startswith("/static/admin/"):
            # Admin assets carry no version fingerprint; always revalidate so
            # style/script updates reach the browser without a hard refresh.
            response.headers["Cache-Control"] = "no-cache"
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        content_type = (response.headers.get("Content-Type") or "").lower()
        if "text/html" in content_type:
            # The Jinja admin templates carry small inline <script> blocks, so they
            # still need script-src 'unsafe-inline'. The built SPA has none, so the
            # public shell gets the stricter policy — that keeps a hypothetical
            # sanitizer bypass on an article page from executing.
            is_admin_html = request.path == self.admin_prefix or request.path.startswith(
                f"{self.admin_prefix}/"
            )
            script_src = "'self' 'unsafe-inline'" if is_admin_html else "'self'"
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "img-src 'self' data: blob: https:; "
                "style-src 'self' 'unsafe-inline'; "
                f"script-src {script_src}; "
                "font-src 'self' data:; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'",
            )
        if settings.cookie_secure and settings.hsts_max_age > 0:
            response.headers.setdefault(
                "Strict-Transport-Security", f"max-age={settings.hsts_max_age}; includeSubDomains"
            )
        return response

    # ------------------------------------------------------------------
    # 装饰器
    # ------------------------------------------------------------------

    def admin_required(self, view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not self.is_authenticated():
                if self.is_admin_api_request() or request.is_json:
                    return api_error("auth_required", "登录状态已失效，请重新登录。", 401)
                return redirect(url_for("admin_login", next=request.path))
            session.permanent = True
            return view_func(*args, **kwargs)

        return wrapped
