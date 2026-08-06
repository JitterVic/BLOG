"""启动配置：读取环境变量、校验生产配置强度。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta

from .env_loader import env_bool, env_int

DEFAULT_SECRET_KEY = "dev-secret-key-change-me"
DEFAULT_ADMIN_PASSWORD = "admin123456"

WEAK_SECRET_KEYS = {DEFAULT_SECRET_KEY, "change-me-before-deploy", "replace-with-a-random-secret"}
WEAK_ADMIN_PASSWORDS = {
    DEFAULT_ADMIN_PASSWORD, "123", "123456", "admin", "password",
    "change-me-before-deploy", "replace-with-a-strong-password",
}


def normalize_admin_prefix(raw_value: str | None) -> str:
    value = (raw_value or "/admin").strip() or "/admin"
    if not value.startswith("/"):
        value = f"/{value}"
    value = value.rstrip("/")
    return value or "/admin"


def validate_launch_config(
    *,
    debug_mode: bool,
    secret_key: str,
    admin_password: str,
    admin_prefix: str,
    public_base_url: str,
    cookie_secure: bool,
    require_public_base_url: bool = False,
) -> None:
    if debug_mode:
        return

    if not secret_key or secret_key in WEAK_SECRET_KEYS or len(secret_key) < 32:
        raise RuntimeError(
            "BLOG_SECRET_KEY 仍是默认值或过短，请在 .env 中改为随机的长密钥。"
        )
    if (
        not admin_password
        or len(admin_password) < 12
        or admin_password in WEAK_ADMIN_PASSWORDS
    ):
        raise RuntimeError(
            "BLOG_ADMIN_PASSWORD 太弱或仍是默认值，请在 .env 中改为至少 12 位的强密码。"
        )
    if admin_prefix == "/admin" or not admin_prefix.startswith("/"):
        raise RuntimeError(
            "BLOG_ADMIN_PREFIX 不能使用默认的 /admin，请改成不易猜到且以 / 开头的路径。"
        )
    if require_public_base_url and not public_base_url:
        raise RuntimeError(
            "上线模式要求配置 BLOG_PUBLIC_BASE_URL 为真实的 HTTPS 公开域名。"
        )
    if public_base_url:
        if not public_base_url.startswith("https://"):
            raise RuntimeError(
                "BLOG_PUBLIC_BASE_URL 必须以 https:// 开头。"
            )
        if not cookie_secure:
            raise RuntimeError(
                "站点已使用 HTTPS，必须同时设置 BLOG_COOKIE_SECURE=true。"
            )


@dataclass(frozen=True)
class LaunchSettings:
    debug_mode: bool
    secret_key: str
    admin_password: str
    admin_prefix: str
    public_base_url: str
    require_public_base_url: bool
    cookie_secure: bool
    hsts_max_age: int
    session_lifetime: timedelta
    max_upload_bytes: int
    login_window_seconds: int
    login_max_attempts: int
    trusted_proxy_count: int


def load_launch_settings() -> LaunchSettings:
    """读取并校验环境变量中的启动配置。"""
    debug_mode = env_bool("BLOG_DEBUG", False)
    secret_key = os.getenv("BLOG_SECRET_KEY", DEFAULT_SECRET_KEY)
    admin_password = os.getenv("BLOG_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    admin_prefix = normalize_admin_prefix(os.getenv("BLOG_ADMIN_PREFIX", "/admin"))
    public_base_url = (os.getenv("BLOG_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    require_public_base_url = env_bool("BLOG_REQUIRE_PUBLIC_BASE_URL", False)
    cookie_secure = env_bool("BLOG_COOKIE_SECURE", False)
    hsts_max_age = env_int("BLOG_HSTS_MAX_AGE", 31536000, minimum=0)
    validate_launch_config(
        debug_mode=debug_mode,
        secret_key=secret_key,
        admin_password=admin_password,
        admin_prefix=admin_prefix,
        public_base_url=public_base_url,
        cookie_secure=cookie_secure,
        require_public_base_url=require_public_base_url,
    )
    return LaunchSettings(
        debug_mode=debug_mode,
        secret_key=secret_key,
        admin_password=admin_password,
        admin_prefix=admin_prefix,
        public_base_url=public_base_url,
        require_public_base_url=require_public_base_url,
        cookie_secure=cookie_secure,
        hsts_max_age=hsts_max_age,
        session_lifetime=timedelta(
            seconds=env_int("BLOG_SESSION_LIFETIME_SECONDS", 8 * 60 * 60, minimum=300)
        ),
        max_upload_bytes=env_int("BLOG_MAX_UPLOAD_BYTES", 10 * 1024 * 1024, minimum=1),
        login_window_seconds=env_int("BLOG_LOGIN_RATE_WINDOW_SECONDS", 300, minimum=60),
        login_max_attempts=env_int("BLOG_LOGIN_MAX_ATTEMPTS", 5, minimum=1),
        trusted_proxy_count=env_int("BLOG_TRUSTED_PROXY_COUNT", 0, minimum=0),
    )
