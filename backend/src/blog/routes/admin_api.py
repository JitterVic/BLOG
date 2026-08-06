"""管理后台 JSON API 路由：自动保存、版本、素材、预览、导入与校验。"""

from __future__ import annotations

from flask import jsonify, request

from ..markdown_tools import estimate_read_time, render_markdown
from ..security import api_error
from ..services.post_service import PostVersionConflict


def register(bp, *, store, security) -> None:
    @security.admin_required
    def admin_autosave():
        payload = request.get_json(silent=True) or {}
        raw_post_id = payload.get("post_id")
        try:
            post_id = int(raw_post_id) if raw_post_id else None
        except (TypeError, ValueError):
            return api_error("invalid_post_id", "稿件 ID 无效。", 400)

        form_data = payload.get("fields") or {}
        if not isinstance(form_data, dict):
            return api_error("invalid_payload", "自动保存数据格式无效。", 400)

        existing = store.get_post_by_id(post_id) if post_id else None
        if post_id and existing is None:
            return api_error("post_not_found", "稿件不存在。", 404)
        if existing and existing.get("status") == "trashed":
            return api_error("trashed_autosave_blocked", "回收站文章不能自动保存。", 409)

        if existing and existing.get("status") == "published":
            expected_updated_at = payload.get("updated_at")
            try:
                store.save_post(
                    form_data,
                    post_id=post_id,
                    action="update",
                    expected_updated_at=expected_updated_at,
                    create_revision=False,
                    allow_untitled=True,
                )
            except PostVersionConflict as exc:
                return api_error("version_conflict", str(exc), 409)
            except ValueError as exc:
                return api_error("validation_error", str(exc), 400)
            saved_post = store.get_post_by_id(post_id) or {}
            return jsonify({
                "id": post_id,
                "slug": saved_post.get("slug", ""),
                "status": saved_post.get("status", "published"),
                "edit_source": "post",
                "updated_at": saved_post.get("updated_at", ""),
                "read_time": saved_post.get("read_time", ""),
                "excerpt": saved_post.get("excerpt", ""),
            })

        expected_updated_at = payload.get("updated_at")
        try:
            saved_id = store.save_post(
                form_data,
                post_id=post_id,
                action="draft",
                expected_updated_at=expected_updated_at,
                create_revision=False,
                allow_untitled=True,
            )
        except PostVersionConflict as exc:
            return api_error("version_conflict", str(exc), 409)
        except ValueError as exc:
            return api_error("validation_error", str(exc), 400)

        saved_post = store.get_post_by_id(saved_id)
        return jsonify({
            "id": saved_id,
            "slug": saved_post.get("slug", ""),
            "status": saved_post.get("status", "draft"),
            "edit_source": "post",
            "updated_at": saved_post.get("updated_at", ""),
            "read_time": saved_post.get("read_time", ""),
            "excerpt": saved_post.get("excerpt", ""),
        })

    @security.admin_required
    def admin_create_checkpoint(post_id):
        try:
            revision_id = store.create_checkpoint(post_id)
        except ValueError as exc:
            return api_error("checkpoint_failed", str(exc), 400)
        security.audit("revision.checkpoint", post_id=post_id, revision_id=revision_id)
        return jsonify({"ok": True, "revision_id": revision_id, "message": "已保存一个关键版本。"})

    @security.admin_required
    def admin_media_api():
        query = (request.args.get("q") or "").strip().lower()
        reference_state = (request.args.get("reference_state") or "").strip()
        items = store.list_media_assets()
        if query:
            items = [
                item for item in items
                if query in item.get("filename", "").lower()
                or query in item.get("original_filename", "").lower()
                or any(query in ref.get("title", "").lower() for ref in item.get("references", []))
            ]
        if reference_state == "referenced":
            items = [item for item in items if item.get("reference_count")]
        elif reference_state == "unreferenced":
            items = [item for item in items if not item.get("reference_count")]
        return jsonify({"items": items, "total": len(items)})

    @security.admin_required
    def admin_preview_markdown():
        payload = request.get_json(silent=True) or {}
        markdown_content = payload.get("markdown_content", "")
        if not isinstance(markdown_content, str):
            return api_error("invalid_payload", "Markdown 内容格式无效。", 400)
        if len(markdown_content) > 500_000:
            return api_error("content_too_large", "Markdown 内容过长。", 400)
        return jsonify(
            {
                "html": render_markdown(markdown_content),
                "read_time": estimate_read_time(markdown_content),
                "excerpt": store.build_excerpt(markdown_content),
            }
        )

    @security.admin_required
    def admin_import_markdown():
        markdown_file = request.files.get("markdown_file")
        if markdown_file is None or not markdown_file.filename:
            return api_error("validation_error", "请选择一个 Markdown 文件。", 400)
        try:
            payload = store.import_markdown(markdown_file)
        except ValueError as exc:
            return api_error("validation_error", str(exc), 400)
        return jsonify(payload)

    @security.admin_required
    def admin_upload_image():
        image_file = request.files.get("image")
        if image_file is None or not image_file.filename:
            return api_error("validation_error", "请选择一张图片。", 400)
        try:
            payload = store.upload_media(image_file)
        except ValueError as exc:
            return api_error("validation_error", str(exc), 400)
        security.audit("media.uploaded", filename=payload.get("filename"))
        return jsonify(payload)

    @security.admin_required
    def admin_validate_post():
        payload = request.get_json(silent=True) or {}
        fields = payload.get("fields") if isinstance(payload.get("fields"), dict) else payload
        raw_post_id = payload.get("post_id")
        try:
            post_id = int(raw_post_id) if raw_post_id else None
        except (TypeError, ValueError):
            return api_error("invalid_post_id", "稿件 ID 无效。", 400)
        result = store.validate_post_for_publish(fields, post_id=post_id)
        return jsonify(result), (200 if result["ok"] else 400)

    @security.admin_required
    def admin_post_revisions(post_id):
        try:
            items = store.list_post_revisions(post_id)
        except ValueError as exc:
            return api_error("post_not_found", str(exc), 404)
        return jsonify({"items": items, "total": len(items)})

    @security.admin_required
    def admin_post_revision_detail(post_id, revision_id):
        revision = store.get_post_revision(post_id, revision_id)
        if revision is None:
            return api_error("revision_not_found", "历史版本不存在。", 404)
        return jsonify(revision)

    @security.admin_required
    def admin_restore_post_revision(post_id, revision_id):
        try:
            post = store.restore_post_revision(post_id, revision_id)
        except ValueError as exc:
            return api_error("revision_restore_failed", str(exc), 400)
        security.audit("revision.restored", post_id=post_id, revision_id=revision_id)
        return jsonify({
            "ok": True,
            "post_id": post_id,
            "status": post.get("status", "draft"),
            "updated_at": post.get("updated_at", ""),
            "message": "历史版本已恢复。",
        })

    bp.add_url_rule("/api/autosave", "admin_autosave", admin_autosave, methods=["POST"])
    bp.add_url_rule("/api/posts/<int:post_id>/checkpoint", "admin_create_checkpoint", admin_create_checkpoint, methods=["POST"])
    bp.add_url_rule("/api/media", "admin_media_api", admin_media_api, methods=["GET"])
    bp.add_url_rule("/api/preview-markdown", "admin_preview_markdown", admin_preview_markdown, methods=["POST"])
    bp.add_url_rule("/api/import-markdown", "admin_import_markdown", admin_import_markdown, methods=["POST"])
    bp.add_url_rule("/api/upload-image", "admin_upload_image", admin_upload_image, methods=["POST"])
    bp.add_url_rule("/api/validate-post", "admin_validate_post", admin_validate_post, methods=["POST"])
    bp.add_url_rule("/api/posts/<int:post_id>/revisions", "admin_post_revisions", admin_post_revisions, methods=["GET"])
    bp.add_url_rule("/api/posts/<int:post_id>/revisions/<int:revision_id>", "admin_post_revision_detail", admin_post_revision_detail, methods=["GET"])
    bp.add_url_rule("/api/posts/<int:post_id>/revisions/<int:revision_id>/restore", "admin_restore_post_revision", admin_restore_post_revision, methods=["POST"])
