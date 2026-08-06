"""路由层：按职责拆分的蓝图/路由组，统一在此注册。"""

from __future__ import annotations

from . import admin_api, admin_auth, admin_pages, admin_posts, feed, public, spa


class _AdminRoutes:
    """管理后台路由注册器。

    管理后台的 URL 前缀是运行时配置，且模板中大量使用裸端点名
    （如 ``url_for('admin_dashboard')``），因此不走 Blueprint 命名空间，
    直接以裸端点名注册到应用上。
    """

    def __init__(self, app, prefix: str):
        self._app = app
        self._prefix = prefix

    def add_url_rule(self, rule: str, endpoint: str, view_func, **options) -> None:
        self._app.add_url_rule(self._prefix + rule, endpoint, view_func, **options)


def register_routes(app, *, store, security, settings) -> None:
    """把所有路由挂载到应用上。"""
    app.register_blueprint(public.build_blueprint(store))
    app.register_blueprint(feed.build_blueprint(store))
    app.register_blueprint(spa.build_blueprint(store, settings))

    admin = _AdminRoutes(app, settings.admin_prefix)
    admin_auth.register(admin, security=security, settings=settings)
    admin_pages.register(admin, store=store, security=security, settings=settings)
    admin_posts.register(admin, store=store, security=security)
    admin_api.register(admin, store=store, security=security)
