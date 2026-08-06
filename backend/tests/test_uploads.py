"""uploads 模块级测试：路径白名单、扩展名校验、图片管线。"""

import io

import pytest
from PIL import Image

from blog.uploads import (
    is_allowed_public_upload_path,
    process_uploaded_image_bytes,
    validate_extension,
    validate_image_upload,
)


class FakeStorage:
    def __init__(self, filename, mimetype, stream):
        self.filename = filename
        self.mimetype = mimetype
        self.stream = stream


def png_bytes(width=16, height=16):
    output = io.BytesIO()
    Image.new("RGB", (width, height), "#b45309").save(output, format="PNG")
    output.seek(0)
    return output


def test_public_upload_path_whitelist():
    assert is_allowed_public_upload_path("media/abc.png") is True
    assert is_allowed_public_upload_path("media/../blog.db") is False
    assert is_allowed_public_upload_path("avatars/x.png") is False
    assert is_allowed_public_upload_path("media/evil.svg") is False
    assert is_allowed_public_upload_path("/media/abs.png") is False
    assert is_allowed_public_upload_path("media/%2e%2e/blog.db") is False


def test_validate_extension_reports_allowed_set():
    with pytest.raises(ValueError, match="格式不支持"):
        validate_extension("note.docx", {".md", ".txt"}, "Markdown 文件")
    validate_extension("note.md", {".md", ".txt"}, "Markdown 文件")


def test_validate_image_upload_rejects_extension_mismatch():
    storage = FakeStorage("fake.png", "image/png", io.BytesIO(b"not-an-image"))
    with pytest.raises(ValueError):
        validate_image_upload(storage, max_bytes=1024 * 1024, max_pixels=1_000_000)


def test_validate_image_upload_rejects_content_type_mismatch():
    buffer = png_bytes()
    storage = FakeStorage("real.png", "image/jpeg", buffer)
    with pytest.raises(ValueError, match="不一致"):
        validate_image_upload(storage, max_bytes=1024 * 1024, max_pixels=1_000_000)


def test_validate_image_upload_enforces_size_limit():
    buffer = png_bytes(64, 64)
    storage = FakeStorage("big.png", "image/png", buffer)
    with pytest.raises(ValueError, match="过大"):
        validate_image_upload(storage, max_bytes=16, max_pixels=1_000_000)


def test_validate_image_upload_accepts_valid_png():
    buffer = png_bytes()
    storage = FakeStorage("ok.png", "image/png", buffer)
    raw = validate_image_upload(storage, max_bytes=1024 * 1024, max_pixels=1_000_000)
    assert raw


def test_process_downscales_large_jpeg():
    buffer = io.BytesIO()
    Image.new("RGB", (3000, 900), "#112233").save(buffer, format="JPEG")
    result = process_uploaded_image_bytes(buffer.getvalue())
    with Image.open(io.BytesIO(result)) as image:
        assert max(image.size) <= 1920
        assert image.format == "JPEG"


def test_process_keeps_small_png_bytes_identical():
    raw = png_bytes().getvalue()
    assert process_uploaded_image_bytes(raw) == raw
