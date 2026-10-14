"""上传文件处理：路径常量、扩展名/MIME 校验、图片压缩与公开路径白名单。"""

from __future__ import annotations

import io
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote

from PIL import Image, UnidentifiedImageError

from .env_loader import env_int, project_root

ROOT_DIR = project_root()
STORAGE_DIR = ROOT_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR
DEFAULT_DB_PATH = STORAGE_DIR / "blog.db"

ALLOWED_MARKDOWN_EXTENSIONS = {".md", ".markdown", ".txt"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".jfif"}
UPLOAD_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".jfif"}
IMAGE_FORMAT_EXTENSIONS = {
    "PNG": {".png"}, "JPEG": {".jpg", ".jpeg", ".jfif"},
    "GIF": {".gif"}, "WEBP": {".webp"}, "BMP": {".bmp"},
}
IMAGE_MIME_TYPES = {
    "PNG": {"image/png"}, "JPEG": {"image/jpeg", "image/jpg", "image/pjpeg"},
    "GIF": {"image/gif"}, "WEBP": {"image/webp"},
    "BMP": {"image/bmp", "image/x-ms-bmp"},
}
DEFAULT_MAX_IMAGE_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 20_000_000
PUBLIC_UPLOAD_FOLDERS = {"media"}

MAX_IMAGE_EDGE = 1920
JPEG_RECODE_QUALITY = 85


def get_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def validate_extension(filename: str, allowed_extensions: set[str], label: str) -> None:
    extension = get_extension(filename)
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise ValueError(f"{label}格式不支持，请使用：{allowed}")


def is_allowed_public_upload_path(path: str) -> bool:
    decoded_path = unquote(path or "").replace("\\", "/").strip()
    if not decoded_path or decoded_path.startswith("/"):
        return False

    parts = PurePosixPath(decoded_path).parts
    if len(parts) < 2 or parts[0] not in PUBLIC_UPLOAD_FOLDERS:
        return False
    if any(part in {"", ".", ".."} for part in parts):
        return False

    return get_extension(parts[-1]) in ALLOWED_IMAGE_EXTENSIONS


def process_uploaded_image_bytes(raw_bytes: bytes) -> bytes:
    """Downscale large raster images and strip JPEG EXIF/GPS via re-encode."""
    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            image_format = (image.format or "").upper()
            if image_format not in {"JPEG", "PNG", "WEBP"}:
                return raw_bytes
            image.load()
            working = image
            original_size = working.size
            if image_format == "JPEG" and working.mode not in {"RGB", "L"}:
                working = working.convert("RGB")
            needs_resize = max(original_size) > MAX_IMAGE_EDGE
            if needs_resize:
                working = working.copy()
                working.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), Image.Resampling.LANCZOS)
            # JPEG always re-encoded to drop EXIF/GPS even when dimensions stay.
            if image_format == "JPEG" or needs_resize:
                output = io.BytesIO()
                save_kwargs: dict[str, Any] = {"format": image_format, "optimize": True}
                if image_format in {"JPEG", "WEBP"}:
                    save_kwargs["quality"] = JPEG_RECODE_QUALITY
                working.save(output, **save_kwargs)
                return output.getvalue()
            return raw_bytes
    except (UnidentifiedImageError, OSError, ValueError):
        return raw_bytes


def validate_image_upload(file_storage, *, max_bytes: int, max_pixels: int) -> bytes:
    filename = (file_storage.filename or "").strip()
    extension = get_extension(filename)
    validate_extension(filename, UPLOAD_IMAGE_EXTENSIONS, "图片")
    mimetype = (file_storage.mimetype or "").lower().split(";", 1)[0].strip()
    if mimetype and not mimetype.startswith("image/"):
        raise ValueError("图片 MIME 类型无效，请选择真实的图片文件。")
    stream = file_storage.stream
    stream.seek(0)
    raw_bytes = stream.read(max_bytes + 1)
    stream.seek(0)
    if len(raw_bytes) > max_bytes:
        raise ValueError(f"图片过大，请控制在 {max_bytes // (1024 * 1024)} MB 以内。")
    if not raw_bytes:
        raise ValueError("图片文件为空。")
    try:
        with Image.open(io.BytesIO(raw_bytes)) as image:
            image_format = (image.format or "").upper()
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("图片内容无法识别，请上传有效的图片文件。") from exc
    if image_format not in IMAGE_FORMAT_EXTENSIONS or extension not in IMAGE_FORMAT_EXTENSIONS[image_format]:
        raise ValueError("图片扩展名、MIME 类型与真实图片格式不一致。")
    if mimetype and mimetype not in IMAGE_MIME_TYPES.get(image_format, set()):
        raise ValueError("图片 MIME 类型与真实图片格式不一致。")
    if width <= 0 or height <= 0 or width * height > max_pixels:
        raise ValueError(f"图片尺寸过大，请控制在 {max_pixels:,} 像素以内。")
    return raw_bytes

