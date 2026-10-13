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


# The "extra" preset bundles attr_list, which lets Markdown emit arbitrary
# attributes — `# H {: onclick="..." }` really does render an onclick handler.
# SafeHTMLCleaner strips it, but that makes the sanitizer the single point of
# failure. Enumerate extra's other members instead so no event-handler
# attribute can be produced in the first place.
MARKDOWN_EXTENSIONS = [
    "abbr",
    "def_list",
    "fenced_code",
    "footnotes",
    "md_in_html",
    "tables",
    "nl2br",
]

# 围栏代码块的语言标记。含 "markdown"/"md" 的围栏意味着作者写的是「Markdown 源码」
# —— 模板、示例、表格常用这种写法。把它当代码输出会让整段 Markdown 原样显示
# （表格变成一串 |---|---|，标题变成 ## xxx），读者眼里就是「渲染坏了」。
_FENCE_RE = re.compile(r"^(?P<indent>[ ]{0,3})(?P<fence>`{3,}|~{3,})(?P<info>[^\n`]*)$")
_MARKDOWN_FENCE_LANGS = {"markdown", "md", "mdown", "mkd", "gfm"}
# 目录树/流程树用的制表符：这些字符的意义完全依赖等宽对齐，
# 一旦按正文渲染（比例字体 + 段落折行）结构就散了，必须保持原样。
_TREE_CHARS = "├└│─┌┐┘┴┬┼┍┎┏┲┳┿╂╋"
_ATX_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S")
_TABLE_DELIMITER_RE = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(?:\|\s*:?-{1,}:?\s*)+\|?\s*$")


def _has_table_block(body: list[str]) -> bool:
    """判断围栏内容里是否含 GFM 表格（表头行 + |---| 分隔行）。

    分隔行的语法很特殊，正常代码/JSON/目录树里几乎不可能出现，
    因此它是「这段是 Markdown 而非代码」最可靠的判据。
    """
    for index in range(len(body) - 1):
        header = body[index]
        delimiter = body[index + 1]
        if "|" not in header or "|" not in delimiter:
            continue
        if _TABLE_DELIMITER_RE.match(delimiter):
            return True
    return False


def _looks_like_markdown_body(body: list[str]) -> bool:
    """围栏内容是否应作为 Markdown 渲染，而不是原样输出为代码。

    只有在判据足够可靠时才还原，避免把真正的代码块（JSON、YAML、目录树、
    命令输出）误渲染成正文：
    - 含 GFM 表格分隔行：代码里不会出现这种写法；
    - 整块只由标题与列表项构成：就是一篇用列表写成的文档片段。
    其余情况（含制表符树、YAML 键值、JSON 花括号、普通代码）一律保持代码块。
    """
    meaningful = [line for line in body if line.strip()]
    if not meaningful:
        return False

    if any(char in line for line in meaningful for char in _TREE_CHARS):
        return False

    if _has_table_block(meaningful):
        return True

    # 整块都是标题/列表项才认定为 Markdown；含普通句子的段落不算，
    # 因为「一段用围栏框起来的散文」在 Markdown 里通常就是要有意保持原样。
    return all(_ATX_HEADING_RE.match(line) or _LIST_ITEM_RE.match(line) for line in meaningful)


def _is_markdown_fence(lang: str, body: list[str]) -> bool:
    if lang in _MARKDOWN_FENCE_LANGS:
        return True
    # 带其它语言标记的围栏是显式代码（json/yaml/bash…），不做推断。
    if lang:
        return False
    return _looks_like_markdown_body(body)


def _demote_headings(body: list[str]) -> list[str]:
    """把围栏内 Markdown 的标题整体降一级。

    围栏里的模板自带自己的根级标题（如快照模板的 `# 2026-07-23`），直接还原会在
    正文中间插进第二个 h1，与文章标题抢层级；降一级后原生标题变成 h2，正好与
    文章的章节同级，模板内部的 `##`/`###` 也顺势落到 h3/h4，层级保持连续。
    """
    demoted: list[str] = []
    for line in body:
        match = re.match(r"^( {0,3})(#{1,5})(?!#)", line)
        demoted.append(
            f"{match.group(1)}#{match.group(2)}{line[match.end():]}" if match else line
        )
    return demoted


def _demote_top_level_headings(markdown_text: str) -> str:
    """把正文里的 ATX 一级标题降为二级。

    文章标题由页面自己的 <h1> 承担，正文再出现 `#` 会让章节与标题同级
    （实测同一篇文章里 `<h1>第一题 两数相加</h1>` 与 h1 文章标题并存，
    而且 `.print-markdown h1` 没有章节样式，看起来像没渲染）。
    把正文的 `#` 统一降为 `##` 后，层级变成「标题 h1 → 章节 h2」，与站点排版一致。

    只处理围栏外的行：代码块里的 `# class ListNode:` 是注释，不能被改。
    """
    lines = (markdown_text or "").split("\n")
    out: list[str] = []
    open_fence: str | None = None
    close_pattern: re.Pattern[str] | None = None

    for line in lines:
        if open_fence is None:
            match = _FENCE_RE.match(line)
            if match:
                open_fence = match.group("fence")
                close_pattern = re.compile(
                    rf"^[ ]{{0,3}}{re.escape(open_fence[0])}{{{len(open_fence)},}}\s*$"
                )
                out.append(line)
                continue
            # Python-Markdown 把 `#标题`/`#hashtag` 也当标题（不要求空格），
            # 这里必须同样宽松，否则漏降级的 h1 仍会与文章标题同级。
            heading = re.match(r"^( {0,3})#(?!#)", line)
            out.append(f"{heading.group(1)}##{line[heading.end():]}" if heading else line)
            continue

        out.append(line)
        if close_pattern and close_pattern.match(line):
            open_fence = None
            close_pattern = None

    return "\n".join(out)


def unwrap_markdown_fences(markdown_text: str) -> tuple[str, int]:
    """把「内容其实是 Markdown」的围栏块还原为其内部源码。

    两类围栏会被还原：
    1. 语言标记明确写着 markdown/md 的（作者显式声明）；
    2. 无语言标记、但内容可判定为 Markdown 的（表格、纯标题/列表块）。
    带其它语言标记的围栏、JSON/YAML/目录树/普通代码一律保持不变。

    必须用「开/收两态」扫描：```` ``` ```` 这种无语言标记的收栏行与无标记的开栏行
    写法完全相同，只看单行无法区分。若把收栏行误当成新的开栏行，它会一路吞到
    下一个 `` ``` ``，把中间的代码块和正文全部吃掉（实测会把一个 json 块和紧随其后的
    markdown 模板块并成一块，json 的收栏行被删掉，导致后面 60 行 Markdown 全被
    当成 json 代码输出）。按状态判断即可彻底消除这种歧义。

    返回 (处理后的文本, 还原的围栏块数量)。
    """
    lines = (markdown_text or "").split("\n")
    out: list[str] = []
    unwrapped = 0

    open_index: int | None = None
    open_fence = ""
    open_lang = ""
    close_pattern: re.Pattern[str] | None = None
    body: list[str] = []

    def flush(*, closing_index: int | None) -> None:
        """收口当前围栏：按判定结果还原内容或原样输出。"""
        nonlocal unwrapped
        assert open_index is not None
        if closing_index is not None and _is_markdown_fence(open_lang, body):
            # 内容整体缩进时先左移到同一基准，避免还原后仍被当作缩进代码块
            indents = [len(line) - len(line.lstrip(" ")) for line in body if line.strip()]
            trim = min(indents) if indents else 0
            dedented = [line[trim:] if len(line) >= trim else line for line in body]
            out.extend(_demote_headings(dedented))
            unwrapped += 1
            return
        out.append(lines[open_index])
        out.extend(body)
        if closing_index is not None:
            out.append(lines[closing_index])

    for index, line in enumerate(lines):
        if open_index is None:
            match = _FENCE_RE.match(line)
            if not match:
                out.append(line)
                continue
            open_index = index
            open_fence = match.group("fence")
            info = match.group("info").strip().split()
            open_lang = info[0].split(":")[0].lower() if info else ""
            close_pattern = re.compile(
                rf"^[ ]{{0,3}}{re.escape(open_fence[0])}{{{len(open_fence)},}}\s*$"
            )
            body = []
            continue

        if close_pattern and close_pattern.match(line):
            flush(closing_index=index)
            open_index = None
            close_pattern = None
            continue

        body.append(line)

    # 未闭合的围栏：不还原，原样输出（与 Python-Markdown 的处理保持一致）
    if open_index is not None:
        flush(closing_index=None)

    return "\n".join(out), unwrapped


def render_markdown(markdown_text: str) -> str:
    # Rich-text paste often carries NBSP (U+00A0) indentation; rendered code
    # copied back out would then fail to run, so normalize before rendering.
    normalized = (markdown_text or "").replace("\xa0", " ")
    unwrapped, _ = unwrap_markdown_fences(normalized)
    rendered = markdown_lib.markdown(_demote_top_level_headings(unwrapped), extensions=MARKDOWN_EXTENSIONS)
    return sanitize_html(rendered)
