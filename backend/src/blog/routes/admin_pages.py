"""管理后台页面路由：仪表盘、写作台、素材库、资料页与全页预览。"""

from __future__ import annotations

from flask import abort, flash, redirect, render_template, request, url_for

from ..serializers import build_edit_post, build_profile_form


def build_admin_context(store, admin_prefix: str, **extra):
    stats = store.stats()
    stats["admin_prefix"] = admin_prefix
    return {"stats": stats, **extra}


def register(bp, *, store, security, settings) -> None:
    admin_prefix = settings.admin_prefix

    @security.admin_required
    def admin_dashboard():
        store.purge_expired_trash(retention_days=30)
        admin_posts = store.list_admin_posts()
        continue_post = next(
            (item for item in admin_posts if item.get("status") == "draft"),
            admin_posts[0] if admin_posts else None,
        )
        health = store.content_health()
        return render_template(
            "admin_dashboard.html",
            **build_admin_context(
                store,
                admin_prefix,
                admin_posts=admin_posts,
                continue_post=continue_post,
                content_health=health,
                attention_items=store.author_attention_items(),
            ),
        )

    @security.admin_required
    def admin_write(post_id):
        post = store.get_post_by_id(post_id) if post_id else None
        if post_id and post is None:
            abort(404)
        if post and post.get("status") == "trashed":
            flash("请先从稿件总览恢复文章，再继续编辑。", "error")
            return redirect(url_for("admin_dashboard"))
        return render_template(
            "admin_write.html",
            **build_admin_context(
                store,
                admin_prefix,
                edit_post=build_edit_post(post),
                media_assets=store.list_media_assets(),
                taxonomy=store.list_taxonomy(),
            ),
        )

    @security.admin_required
    def admin_media():
        return render_template(
            "admin_media.html",
            **build_admin_context(store, admin_prefix, media_assets=store.list_media_assets()),
        )

    @security.admin_required
    def admin_profile_page():
        profile = store.get_site_profile()
        return render_template(
            "admin_profile.html",
            **build_admin_context(
                store,
                admin_prefix,
                profile_form=build_profile_form(profile),
            ),
        )

    @security.admin_required
    def admin_profile():
        try:
            store.update_site_profile(request.form)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            security.audit("profile.updated")
            flash("个人资料已更新。", "success")
        return redirect(url_for("admin_profile_page"))

    @security.admin_required
    def admin_full_preview(post_id):
        post = store.get_post_by_id(post_id)
        if post is None:
            abort(404)
        preview_post = build_edit_post(post)
        return render_template("admin_preview.html", preview_post=preview_post)

    bp.add_url_rule("", "admin_dashboard", admin_dashboard, methods=["GET"])
    bp.add_url_rule(
        "/write", "admin_write", admin_write, methods=["GET"], defaults={"post_id": None}
    )
    bp.add_url_rule("/write/<int:post_id>", "admin_write", admin_write, methods=["GET"])
    bp.add_url_rule("/media", "admin_media", admin_media, methods=["GET"])
    bp.add_url_rule("/profile", "admin_profile_page", admin_profile_page, methods=["GET"])
    bp.add_url_rule("/profile", "admin_profile", admin_profile, methods=["POST"])
    bp.add_url_rule("/preview/<int:post_id>", "admin_full_preview", admin_full_preview, methods=["GET"])
