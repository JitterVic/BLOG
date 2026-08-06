"""security 模块级测试：密码比较、跳转白名单、限流窗口与启动校验。"""

import importlib

import pytest

from blog.security import (
    api_error,
    is_safe_admin_next,
    passwords_match,
    safe_referrer_target,
)


def test_passwords_match_constant_time_and_unicode_safe():
    assert passwords_match("密码-αβγ", "密码-αβγ") is True
    assert passwords_match("密码", "其他") is False
    assert passwords_match(None, "x") is False
    assert passwords_match("x", None) is False


def test_is_safe_admin_next_rejects_external_targets():
    assert is_safe_admin_next("/admin/dashboard", "/admin") is True
    assert is_safe_admin_next("/admin", "/admin") is False
    assert is_safe_admin_next("https://evil.example/admin/x", "/admin") is False
    assert is_safe_admin_next("//evil.example", "/admin") is False
    assert is_safe_admin_next(None, "/admin") is False


def test_safe_referrer_target_only_trusts_same_admin_area():
    assert safe_referrer_target("https://site.test/admin/write", "/admin", "site.test") == "https://site.test/admin/write"
    assert safe_referrer_target("https://evil.test/admin/write", "/admin", "site.test") is None
    assert safe_referrer_target("https://site.test/", "/admin", "site.test") is None
    assert safe_referrer_target("javascript:alert(1)", "/admin", "site.test") is None
    assert safe_referrer_target(None, "/admin", "site.test") is None


def test_api_error_payload_shape():
    from flask import Flask

    with Flask(__name__).app_context():
        response, status = api_error("demo_code", "演示错误", 418)
        assert status == 418
        assert response.get_json() == {"ok": False, "code": "demo_code", "error": "演示错误"}


def test_validate_launch_config_requires_https_and_cookie_secure():
    config_module = importlib.import_module("blog.config")
    base = dict(
        debug_mode=False,
        secret_key="unique-test-secret-key-1234567890abcdef",
        admin_password="strong-enough-password",
        admin_prefix="/launch-admin",
        public_base_url="https://example.com",
        cookie_secure=True,
    )
    config_module.validate_launch_config(**base)

    with pytest.raises(RuntimeError, match="BLOG_COOKIE_SECURE"):
        config_module.validate_launch_config(**{**base, "cookie_secure": False})
    with pytest.raises(RuntimeError, match="BLOG_PUBLIC_BASE_URL"):
        config_module.validate_launch_config(**{**base, "public_base_url": "http://example.com"})


def test_debug_mode_skips_launch_validation():
    config_module = importlib.import_module("blog.config")
    config_module.validate_launch_config(
        debug_mode=True,
        secret_key="",
        admin_password="",
        admin_prefix="/admin",
        public_base_url="",
        cookie_secure=False,
    )
