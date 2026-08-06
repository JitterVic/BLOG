"""媒体服务：上传落盘、素材清单与文章引用扫描。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from .. import uploads
from ..markdown_tools import MEDIA_URL_PATTERN


class MediaService:
    def __init__(self, media_repo, posts_repo, *, max_file_bytes: int, max_image_bytes: int, max_image_pixels: int):
        self.media_repo = media_repo
        self.posts_repo = posts_repo
        self.max_file_bytes = max_file_bytes
        self.max_image_bytes = max_image_bytes
        self.max_image_pixels = max_image_pixels

    def save_file(
        self,
        file_storage,
        folder: str,
        *,
        allowed_extensions: set[str] | None = None,
        label: str = "文件",
    ) -> str:
        original_filename = (file_storage.filename or "file").strip()
        if folder in uploads.PUBLIC_UPLOAD_FOLDERS:
            raw_bytes = uploads.validate_image_upload(
                file_storage, max_bytes=self.max_image_bytes, max_pixels=self.max_image_pixels
            )
            raw_bytes = uploads.process_uploaded_image_bytes(raw_bytes)
        else:
            if allowed_extensions:
                uploads.validate_extension(original_filename, allowed_extensions, label)
            stream = file_storage.stream
            stream.seek(0)
            raw_bytes = stream.read(self.max_file_bytes + 1)
            stream.seek(0)
            if len(raw_bytes) > self.max_file_bytes:
                raise ValueError(f"{label}过大，请控制在 {self.max_file_bytes // (1024 * 1024)} MB 以内。")

        source_path = Path(original_filename)
        suffix = source_path.suffix.lower()
        safe_stem = secure_filename(source_path.stem) or "file"
        unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}-{safe_stem}{suffix}"
        relative_path = Path(folder) / unique_name
        destination = uploads.UPLOADS_DIR / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw_bytes)
        relative_text = relative_path.as_posix()
        if folder == "media":
            self.media_repo.upsert_metadata(relative_text, original_filename)
        return relative_text

    def upload_media(self, file_storage) -> dict[str, str]:
        relative_path = self.save_file(
            file_storage,
            "media",
            allowed_extensions=uploads.UPLOAD_IMAGE_EXTENSIONS,
            label="图片",
        )
        return {
            "path": relative_path,
            "url": "/uploads/" + relative_path,
            "filename": Path(relative_path).name,
            "original_filename": (file_storage.filename or Path(relative_path).name).strip(),
        }

    def _collect_references(self) -> dict[str, list[dict[str, Any]]]:
        references: dict[str, list[dict[str, Any]]] = {}
        for row in self.posts_repo.scan_rows():
            found: set[tuple[str, str]] = set()
            cover_url = str(row["cover_image"] or "")
            if cover_url.startswith("/uploads/media/"):
                found.add((unquote(cover_url.split("?", 1)[0].split("#", 1)[0]), "cover"))
            for match in MEDIA_URL_PATTERN.finditer(str(row["markdown_content"] or "")):
                found.add(("/uploads/media/" + unquote(match.group(1)), "body"))
            for url, kind in found:
                references.setdefault(url, []).append({
                    "post_id": row["id"],
                    "title": row["title"],
                    "slug": row["slug"],
                    "status": row["status"],
                    "kind": kind,
                })
        return references

    def list_media_assets(self) -> list[dict[str, Any]]:
        media_dir = uploads.UPLOADS_DIR / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        references = self._collect_references()
        media_names = self.media_repo.metadata_map()

        assets: list[dict[str, Any]] = []
        for path in media_dir.iterdir():
            if not path.is_file() or path.suffix.lower() not in uploads.UPLOAD_IMAGE_EXTENSIONS:
                continue
            stat = path.stat()
            width = 0
            height = 0
            try:
                with Image.open(path) as image:
                    width, height = image.size
            except (UnidentifiedImageError, OSError, ValueError):
                pass
            url = "/uploads/media/" + path.name
            refs = references.get(url, [])
            fallback_name = re.sub(r"^(?:\d{20}-)+", "", path.name) or path.name
            assets.append({
                "url": url,
                "filename": path.name,
                "original_filename": media_names.get(f"media/{path.name}", "") or fallback_name,
                "size": stat.st_size,
                "width": width,
                "height": height,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "references": refs,
                "reference_count": len(refs),
            })
        assets.sort(key=lambda item: (item["created_at"], item["filename"]), reverse=True)
        return assets
