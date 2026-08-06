"""管理后台文章表单操作路由：保存/删除/恢复/发布/下架/批量操作。"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from ..markdown_tools import render_markdown
from ..serializers import build_edit_post, form_value
from .admin_pages import build_admin_context


def register(bp, *, store, security) -> None:
    @security.admin_required
    def admin_save_post():
        post_id = request.form.get("post_id", type=int)
        action = form_value(request.form, "action", "draft") or "draft"
        existing = store.get_post_by_id(post_id) if post_id else None
        if existing and existing.get("status") == "trashed":
            flash("回收站文章不能直接保存，请先恢复为草稿。", "error")
            return redirect(url_for("admin_dashboard"))
        try:
            saved_id = store.save_post(
                request.form,
                post_id=post_id,
                action=action,
            )
        except ValueError as exc:
            flash(str(exc), "error")
            submitted = build_edit_post(existing)
            submitted.update({
                "id": post_id or "",
                "title": form_value(request.form, "title"),
                "slug": form_value(request.form, "slug"),
                "excerpt": form_value(request.form, "excerpt"),
                "published_at": form_value(request.form, "published_at"),
                "read_time": form_value(request.form, "read_time"),
                "category": form_value(request.form, "category"),
                "tags_text": form_value(request.form, "tags"),
                "hero_quote": form_value(request.form, "hero_quote"),
                "cover_image": form_value(request.form, "cover_image"),
                "markdown_content": str(request.form.get("markdown_content") or ""),
                "html_content": render_markdown(str(request.form.get("markdown_content") or "")),
                "status": (existing or {}).get("status", "draft"),
            })
            return render_template(
                "admin_write.html",
                **build_admin_context(
                    store,
                    security.admin_prefix,
                    edit_post=submitted,
                    media_assets=store.list_media_assets(),
                    taxonomy=store.list_taxonomy(),
                ),
            ), 400

        message = ('已保存为草稿（前台不可见）。若要上线，请点击「发布文章」。' if action == "draft" else '文章已发布，前台现在可以看到。')
        security.audit("post.saved", post_id=saved_id, action=action)
        flash(message, "success")
        return redirect(url_for("admin_write", post_id=saved_id, saved=1))

    @security.admin_required
    def admin_delete_post(post_id):
        try:
            store.trash_post(post_id)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            security.audit("post.trashed", post_id=post_id)
            flash("文章已移入回收站，30 天内可以恢复。", "success")
        return redirect(url_for("admin_dashboard"))

    @security.admin_required
    def admin_restore_post(post_id):
        try:
            store.restore_post(post_id)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            security.audit("post.restored", post_id=post_id)
            flash("文章已恢复为草稿。", "success")
        return redirect(url_for("admin_dashboard"))

    @security.admin_required
    def admin_quick_publish_post(post_id):
        try:
            store.publish_post(post_id)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin_write", post_id=post_id))
        security.audit("post.published", post_id=post_id, source="quick")
        flash("文章已发布，前台现在可以看到。", "success")
        return redirect(url_for("admin_dashboard"))

    @security.admin_required
    def admin_unpublish_post(post_id):
        try:
            store.unpublish_post(post_id)
        except ValueError as exc:
            flash(str(exc), "error")
        else:
            security.audit("post.unpublished", post_id=post_id)
            flash("文章已下架，当前修改已保留为草稿。", "success")
        return redirect(url_for("admin_write", post_id=post_id))

    @security.admin_required
    def admin_bulk_posts():
        action = form_value(request.form, "action")
        handlers = {
            "trash": (store.trash_post, "移入回收站"),
            "restore": (store.restore_post, "恢复为草稿"),
            "purge": (store.purge_post, "彻底删除"),
        }
        handler = handlers.get(action)
        if handler is None:
            flash("不支持的批量操作。", "error")
            return redirect(url_for("admin_dashboard"))
        raw_ids = request.form.getlist("post_ids")
        post_ids: list[int] = []
        for raw_id in raw_ids:
            try:
                post_ids.append(int(raw_id))
            except (TypeError, ValueError):
                continue
        if not post_ids:
            flash("请先勾选要操作的稿件。", "error")
            return redirect(url_for("admin_dashboard"))
        handler_fn, label = handler
        failures: list[str] = []
        success_count = 0
        for target_id in post_ids:
            try:
                handler_fn(target_id)
                success_count += 1
            except ValueError as exc:
                failures.append(str(exc))
        security.audit("post.bulk", action=action, success=success_count, failed=len(failures))
        if success_count:
            flash(f"已{label} {success_count} 篇稿件。", "success")
        if failures:
            flash(f"{len(failures)} 篇操作失败：{failures[0]}", "error")
        return redirect(url_for("admin_dashboard"))

    bp.add_url_rule("/posts/save", "admin_save_post", admin_save_post, methods=["POST"])
    bp.add_url_rule("/posts/<int:post_id>/delete", "admin_delete_post", admin_delete_post, methods=["POST"])
    bp.add_url_rule("/posts/<int:post_id>/restore", "admin_restore_post", admin_restore_post, methods=["POST"])
    bp.add_url_rule("/posts/<int:post_id>/quick-publish", "admin_quick_publish_post", admin_quick_publish_post, methods=["POST"])
    bp.add_url_rule("/posts/<int:post_id>/unpublish", "admin_unpublish_post", admin_unpublish_post, methods=["POST"])
    bp.add_url_rule("/posts/bulk", "admin_bulk_posts", admin_bulk_posts, methods=["POST"])
