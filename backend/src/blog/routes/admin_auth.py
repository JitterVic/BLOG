"""管理后台登录/登出路由。"""

from __future__ import annotations

import logging

from flask import flash, redirect, render_template, request, session, url_for

from ..security import api_error, is_safe_admin_next, passwords_match
from ..serializers import form_value


def register(bp, *, security, settings) -> None:
    def admin_login():
        if request.method == "POST":
            limited, retry_after = security.login_rate_limited()
            if limited:
                security.audit("login.rate_limited", level=logging.WARNING, retry_after=retry_after)
                if request.is_json:
                    return api_error("login_rate_limited", "登录尝试过多，请稍后再试。", 429)
                flash("登录尝试过多，请稍后再试。", "error")
                return render_template("admin_login.html"), 429, {"Retry-After": str(retry_after)}

            password = form_value(request.form, "password")
            if passwords_match(password, settings.admin_password):
                security.login_failures.pop(security.client_key(), None)
                session.clear()
                session.permanent = True
                session["admin_authenticated"] = True
                security.csrf_token()
                security.audit("login.success")
                flash("已进入管理后台。", "success")
                next_target = request.args.get("next")
                if not is_safe_admin_next(next_target, settings.admin_prefix):
                    next_target = url_for("admin_dashboard")
                return redirect(next_target)

            security.register_login_failure()
            security.audit("login.failed", level=logging.WARNING)
            flash("密码错误，请重试。", "error")

        return render_template("admin_login.html")

    @security.admin_required
    def admin_logout():
        security.audit("logout")
        session.clear()
        flash("你已退出后台。", "success")
        return redirect(url_for("admin_login"))

    bp.add_url_rule("/login", "admin_login", admin_login, methods=["GET", "POST"])
    bp.add_url_rule("/logout", "admin_logout", admin_logout, methods=["POST"])
