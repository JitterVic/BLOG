"""Markdown 渲染与 HTML 消毒：白名单标签/属性过滤，拦截危险链接与脚本。"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import markdown as markdown_lib

from .. import uploads

ALLOWED_HTML_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "div",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "s",
    "span",
    "strong",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}
ALLOWED_HTML_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
    "td": {"align", "colspan", "rowspan"},
    "th": {"align", "colspan", "rowspan"},
    "ol": {"start"},
}
HTML_VOID_TAGS = {"br", "hr", "img"}
HTML_DROP_CONTENT_TAGS = {"script", "style", "iframe", "object", "embed", "svg", "math", "template"}
SAFE_CLASS_RE = re.compile(r"^[A-Za-z0-9_\- ]{1,80}$")
SAFE_INT_RE = re.compile(r"^[1-9][0-9]{0,2}$")
URL_SCHEME_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*):")


def _normalize_url_for_scheme(value: str) -> str:
    return re.sub(r"[\x00-\x20]+", "", value or "").lower()


def _has_colon_before_path_marker(value: str) -> bool:
    marker_positions = [pos for marker in ("/", "?", "#") if (pos := value.find(marker)) >= 0]
    first_marker = min(marker_positions) if marker_positions else len(value)
    colon = value.find(":")
    return 0 <= colon < first_marker


def _is_safe_link_url(value: str) -> bool:
    cleaned = (value or "").strip()
    normalized = _normalize_url_for_scheme(cleaned)
    if not cleaned or normalized.startswith("//"):
        return False
    scheme_match = URL_SCHEME_RE.match(normalized)
    if scheme_match:
        return scheme_match.group(1) in {"http", "https", "mailto"}
    return not _has_colon_before_path_marker(normalized)


def _is_safe_image_url(value: str) -> bool:
    cleaned = (value or "").strip()
    normalized = _normalize_url_for_scheme(cleaned)
    if not cleaned or normalized.startswith("//"):
        return False
    scheme_match = URL_SCHEME_RE.match(normalized)
    if scheme_match:
        return scheme_match.group(1) in {"http", "https"}

    parsed = urlsplit(cleaned)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith("/uploads/"):
        return False
    return uploads.is_allowed_public_upload_path(parsed.path.removeprefix("/uploads/"))


def is_safe_image_url(value: str) -> bool:
    """对外暴露的封面图/图片地址安全校验。"""
    return _is_safe_image_url(value)


def _clean_attr(tag: str, name: str, value: str | None) -> tuple[str, str] | None:
    attr = name.lower().strip()
    if attr.startswith("on") or attr not in ALLOWED_HTML_ATTRS.get(tag, set()):
        return None

    cleaned = (value or "").strip()
    if attr == "href" and not _is_safe_link_url(cleaned):
        return None
    if attr == "src" and not _is_safe_image_url(cleaned):
        return None
    if attr == "class" and not SAFE_CLASS_RE.fullmatch(cleaned):
        return None
    if attr in {"colspan", "rowspan", "start"} and not SAFE_INT_RE.fullmatch(cleaned):
        return None
    if attr == "align" and cleaned not in {"left", "center", "right"}:
        return None
    return attr, cleaned


class SafeHTMLCleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.open_tags: list[str] = []
        self.drop_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._append_starttag(tag, attrs, is_self_closing=False)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._append_starttag(tag, attrs, is_self_closing=True)

    def _append_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
        *,
        is_self_closing: bool,
    ) -> None:
        tag = tag.lower()
        if tag in HTML_DROP_CONTENT_TAGS:
            if not is_self_closing:
                self.drop_depth += 1
            return
        if self.drop_depth or tag not in ALLOWED_HTML_TAGS:
            return

        cleaned_attrs = []
        for name, value in attrs:
            cleaned = _clean_attr(tag, name, value)
            if cleaned:
                attr, attr_value = cleaned
                cleaned_attrs.append(f'{attr}="{html.escape(attr_value, quote=True)}"')

        attr_text = " " + " ".join(cleaned_attrs) if cleaned_attrs else ""
        self.parts.append(f"<{tag}{attr_text}>")
        if tag not in HTML_VOID_TAGS and not is_self_closing:
            self.open_tags.append(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in HTML_DROP_CONTENT_TAGS:
            if self.drop_depth:
                self.drop_depth -= 1
            return
        if self.drop_depth or tag not in ALLOWED_HTML_TAGS or tag in HTML_VOID_TAGS:
            return
        if tag in self.open_tags:
            while self.open_tags:
                open_tag = self.open_tags.pop()
                self.parts.append(f"</{open_tag}>")
                if open_tag == tag:
                    break

    def handle_data(self, data: str) -> None:
        if not self.drop_depth:
            self.parts.append(html.escape(data))

    def get_html(self) -> str:
        while self.open_tags:
            self.parts.append(f"</{self.open_tags.pop()}>")
        return "".join(self.parts)


def sanitize_html(html_text: str) -> str:
    cleaner = SafeHTMLCleaner()
    cleaner.feed(html_text or "")
    cleaner.close()
    return cleaner.get_html()


def render_markdown(markdown_text: str) -> str:
    # Rich-text paste often carries NBSP (U+00A0) indentation; rendered code
    # copied back out would then fail to run, so normalize before rendering.
    rendered = markdown_lib.markdown(
        (markdown_text or "").replace("\xa0", " "),
        extensions=["extra", "fenced_code", "tables", "nl2br"],
    )
    return sanitize_html(rendered)
