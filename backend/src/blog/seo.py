"""SEO 输出：Atom feed、sitemap、robots.txt 与 SPA 页面的 meta 注入。"""

from __future__ import annotations

import html as html_lib
import os
import re
from datetime import datetime, timezone
from typing import Any, Callable
from xml.sax.saxutils import escape as xml_escape

from flask import request


def public_base_url() -> str:
    configured = (os.getenv("BLOG_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if configured:
        return configured
    return request.url_root.rstrip("/")


def absolute_url(path: str) -> str:
    base = public_base_url()
    if not path:
        return base + "/"
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = "/" + path
    return base + path


def _utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def atom_datetime(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return _utc_now_stamp()
    if "T" in text:
        return text if text.endswith("Z") else text + "Z" if len(text) == 19 else text
    if len(text) >= 10:
        return text[:10] + "T00:00:00Z"
    return _utc_now_stamp()


# XML 1.0 forbids C0 controls other than tab/LF/CR outright — they cannot even
# be escaped as character references. Feed readers reject the whole document,
# so strip them before they reach <title>/<summary>.
ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def strip_illegal_xml_chars(value: str) -> str:
    return ILLEGAL_XML_CHARS_RE.sub("", str(value or ""))


def _xml_text(value: str) -> str:
    return xml_escape(strip_illegal_xml_chars(value))


def _xml_attr(value: str) -> str:
    return xml_escape(strip_illegal_xml_chars(value), {'"': "&quot;", "'": "&apos;"})


def build_atom_feed(store) -> str:
    base = public_base_url()
    posts = store.list_posts(published_only=True, sort="latest", limit=20)
    updated = atom_datetime(posts[0].get("updated_at") or posts[0].get("published_at") if posts else None)
    entries: list[str] = []
    for post in posts:
        link = absolute_url(f"/posts/{post['slug']}")
        title = _xml_text(post.get("title") or "")
        summary = _xml_text(post.get("excerpt") or "")
        entry_updated = atom_datetime(post.get("updated_at") or post.get("published_at"))
        entries.append(
            "\n".join(
                [
                    "  <entry>",
                    f"    <title>{title}</title>",
                    f'    <link href="{_xml_attr(link)}" rel="alternate" type="text/html"/>',
                    f"    <id>{_xml_text(link)}</id>",
                    f"    <updated>{entry_updated}</updated>",
                    f'    <summary type="text">{summary}</summary>',
                    "  </entry>",
                ]
            )
        )
    feed = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        "  <title>至知</title>",
        "  <subtitle>记录技术实践、项目复盘和长期学习的个人博客</subtitle>",
        f'  <link href="{_xml_attr(absolute_url("/feed.xml"))}" rel="self" type="application/atom+xml"/>',
        f'  <link href="{_xml_attr(base + "/")}" rel="alternate" type="text/html"/>',
        f"  <id>{_xml_text(base + '/')}</id>",
        f"  <updated>{updated}</updated>",
        *entries,
        "</feed>",
        "",
    ]
    return "\n".join(feed)


def build_sitemap(store) -> str:
    posts = store.list_posts(published_only=True, sort="latest")
    urls: list[tuple[str, str | None]] = [
        ("/", None),
        ("/posts", None),
        ("/about", None),
    ]
    for post in posts:
        lastmod = (post.get("updated_at") or post.get("published_at") or "")[:10] or None
        urls.append((f"/posts/{post['slug']}", lastmod))
    parts = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path, lastmod in urls:
        parts.append("  <url>")
        parts.append(f"    <loc>{_xml_text(absolute_url(path))}</loc>")
        if lastmod:
            parts.append(f"    <lastmod>{_xml_text(lastmod)}</lastmod>")
        parts.append("  </url>")
    parts.append("</urlset>")
    parts.append("")
    return "\n".join(parts)


def build_robots_txt() -> str:
    return "User-agent: *\nAllow: /\nSitemap: " + absolute_url("/sitemap.xml") + "\n"


def inject_post_meta(html_text: str, post: dict[str, Any], url_builder: Callable[[str], str]) -> str:
    """为文章页 SPA 外壳注入 title/description/OG/canonical 元信息。"""
    title = str(post.get("title") or "至知")
    description = str(post.get("excerpt") or "至知：记录技术实践、项目复盘和长期学习的个人博客。")
    page_url = url_builder(f"/posts/{post['slug']}")
    safe_title = html_lib.escape(title, quote=True)
    safe_desc = html_lib.escape(description, quote=True)
    safe_page_url = html_lib.escape(page_url, quote=True)
    # Post text reaches re.sub as the *replacement*, where Python expands \1,
    # \g<name> and friends. A title or auto-excerpt holding a backslash escape
    # (regex tutorials, Windows paths) would raise re.error and 500 the page,
    # so pass a callable — its return value is used verbatim.
    html_text = re.sub(
        r"<title>.*?</title>",
        lambda _match: f"<title>{html_lib.escape(title)} · 至知</title>",
        html_text,
        count=1,
        flags=re.I | re.S,
    )
    desc_pattern = r"<meta[^>]*name=[\"']description[\"'][^>]*/?>"
    if re.search(desc_pattern, html_text, flags=re.I | re.S):
        html_text = re.sub(
            desc_pattern,
            lambda _match: f'<meta name="description" content="{safe_desc}" />',
            html_text,
            count=1,
            flags=re.I | re.S,
        )
    else:
        html_text = html_text.replace(
            "</head>",
            f'    <meta name="description" content="{safe_desc}" />\n  </head>',
            1,
        )
    cover = str(post.get("cover_image") or "").strip()
    og_image_tag = ""
    if cover:
        og_image = url_builder(cover)
        og_image_tag = f'    <meta property="og:image" content="{html_lib.escape(og_image, quote=True)}" />\n'
    og_block = (
        f'    <meta property="og:title" content="{safe_title}" />\n'
        f'    <meta property="og:description" content="{safe_desc}" />\n'
        f'    <meta property="og:type" content="article" />\n'
        f'    <meta property="og:url" content="{safe_page_url}" />\n'
        f"{og_image_tag}"
        f'    <link rel="canonical" href="{safe_page_url}" />\n'
    )
    return html_text.replace("</head>", og_block + "  </head>", 1)
