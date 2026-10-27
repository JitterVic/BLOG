// 文章正文 DOM 增强：外链安全、图片灯箱、代码复制按钮、标题锚点。
// 所有增强均可通过返回的 cleanup 函数完整撤销。

import { highlightDeclared } from "./highlight";

export async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function enhanceExternalLinks(body, tracked) {
  body.querySelectorAll("a[href]").forEach((anchor) => {
    const url = new URL(anchor.href, window.location.href);
    if (["http:", "https:"].includes(url.protocol) && url.origin !== window.location.origin) {
      anchor.target = "_blank";
      anchor.rel = "noopener";
    }
  });
}

function enhanceImages(body, tracked, openLightbox) {
  body.querySelectorAll("img").forEach((image) => {
    image.loading = "lazy";
    image.decoding = "async";
    image.setAttribute("decoding", "async");
    image.tabIndex = 0;
    image.setAttribute("role", "button");
    image.setAttribute("aria-label", `放大图片：${image.alt || "文章插图"}`);
    const openHandler = () => openLightbox(image);
    const errorHandler = () => image.classList.add("is-broken");
    const keyHandler = (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openLightbox(image);
    };
    image.addEventListener("click", openHandler);
    image.addEventListener("error", errorHandler);
    image.addEventListener("keydown", keyHandler);
    tracked.push({ element: image, event: "click", handler: openHandler });
    tracked.push({ element: image, event: "error", handler: errorHandler });
    tracked.push({ element: image, event: "keydown", handler: keyHandler });
  });
}

function enhanceCodeBlocks(body, tracked) {
  body.querySelectorAll("pre").forEach((pre) => {
    const code = pre.querySelector("code");
    if (!code || pre.querySelector(".code-toolbar")) return;

    // 只高亮显式声明且已注册的语言；无标记的围栏（目录树、YAML、表格）
    // 一律按纯文本处理，避免 hljs 自动猜测出错误的 token 配色。
    const language = highlightDeclared(code);
    const label = pre.getAttribute("data-lang") || (language ? language.toUpperCase() : "代码");
    pre.classList.add("has-code-toolbar");

    // 创建顶部工具条：语言名 + 复制（无装饰）
    const toolbar = document.createElement("div");
    toolbar.className = "code-toolbar";

    const langLabel = document.createElement("span");
    langLabel.className = "code-toolbar__lang";
    langLabel.textContent = label;

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "code-copy-button";
    copyBtn.textContent = "复制";
    copyBtn.setAttribute("aria-label", "复制代码");

    let timer = 0;
    const handler = async () => {
      try {
        await copyText(code.textContent || "");
        copyBtn.classList.add("copied");
        copyBtn.textContent = "已复制";
      } catch {
        copyBtn.textContent = "复制失败";
      }
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        copyBtn.classList.remove("copied");
        copyBtn.textContent = "复制";
      }, 1800);
    };

    copyBtn.addEventListener("click", handler);
    toolbar.appendChild(langLabel);
    toolbar.appendChild(copyBtn);

    pre.insertBefore(toolbar, code);
    tracked.push({ element: toolbar, event: "click", type: "node", handler: () => window.clearTimeout(timer) });
    tracked.push({ element: copyBtn, event: "click", handler });
  });
}

function enhanceHeadingAnchors(headings, tracked) {
  headings.forEach((heading) => {
    if (heading.querySelector(":scope > .heading-anchor")) return;
    const anchor = document.createElement("a");
    anchor.className = "heading-anchor";
    anchor.href = `#${heading.id}`;
    anchor.textContent = "#";
    anchor.setAttribute("aria-label", `复制或跳转到章节：${heading.textContent?.trim() || heading.id}`);
    const handler = () => {
      history.replaceState(null, "", `#${heading.id}`);
    };
    anchor.addEventListener("click", handler);
    heading.appendChild(anchor);
    tracked.push({ element: anchor, type: "node", handler });
  });
}

/**
 * 脚注与边注增强（DESIGN.md §5.4）：
 * - 识别正文内 a[href^="#fn"] 引用与文末脚注列表（兼容 SafeHTMLCleaner 清洗后的 DOM）；
 * - ≥1100px：在 .article 右侧批注栏生成 .article-sidenotes 边注列，按引用位置顶对齐，碰撞向下推；
 * - <1100px：点击脚注标号在当前段落后就地展开/收起 .footnote-inline；
 * - 无脚注的文章不挂载边注列，右栏仍有题记与延伸阅读。
 */
function enhanceFootnotes(body, tracked) {
  const article = body.closest(".article");
  if (!article) return;

  const refLinks = Array.from(
    body.querySelectorAll('a[href^="#fn:"], a[href^="#fn-"], a.footnote-ref'),
  );
  if (!refLinks.length) {
    article.classList.remove("article--has-sidenotes");
    return;
  }

  // 查找文末脚注列表：优先找带 backref 链接的 ol，或含 id^="fn" 的 ol
  const backrefs = Array.from(body.querySelectorAll('a[href^="#fnref:"], a[href^="#fnref-"], a.footnote-backref'));
  let footnoteList = backrefs[0]?.closest("ol") || body.querySelector('.footnotes ol, .footnote ol, ol:has(> li[id^="fn"])');
  if (!footnoteList) {
    const allOls = Array.from(body.querySelectorAll("ol"));
    if (allOls.length) {
      const candidate = allOls[allOls.length - 1];
      if (candidate.querySelectorAll("li").length >= refLinks.length) {
        footnoteList = candidate;
      }
    }
  }
  if (!footnoteList) return;

  const footnoteContainer = footnoteList.closest("div") !== body ? footnoteList.closest("div") : footnoteList;
  footnoteContainer?.classList.add("footnotes");

  const listItems = Array.from(footnoteList.querySelectorAll(":scope > li"));
  const itemsByKey = new Map();
  listItems.forEach((li, idx) => {
    li.classList.add("footnotes-item");
    const back = li.querySelector('a[href^="#fnref"]');
    const rawKey = li.id
      ? li.id.replace(/^fn[:\-]?/, "")
      : back?.getAttribute("href")?.replace(/^#fnref[:\-]?/, "") || String(idx + 1);
    if (!li.id) li.id = `fn:${rawKey}`;
    itemsByKey.set(rawKey, { li, index: idx + 1 });
  });

  const pairs = [];
  refLinks.forEach((ref, idx) => {
    const href = ref.getAttribute("href") || "";
    const key = href.replace(/^#fn[:\-]?/, "") || String(idx + 1);
    const matched = itemsByKey.get(key) || (listItems[idx] ? { li: listItems[idx], index: idx + 1 } : null);
    if (!matched) return;

    const num = matched.index;
    ref.classList.add("footnote-ref");
    if (!ref.id) ref.id = `fnref:${key}`;
    const rawLabel = (ref.textContent || "").trim();
    if (/^\d+$/.test(rawLabel)) {
      ref.textContent = `[${rawLabel}]`;
    }
    ref.setAttribute("aria-label", `脚注 ${num}`);

    // 提取纯净的脚注 HTML（去掉文末回跳箭头 ↩）
    const clone = matched.li.cloneNode(true);
    clone.querySelectorAll('a[href^="#fnref"], a.footnote-backref').forEach((el) => el.remove());
    const contentHtml = clone.innerHTML.trim();

    pairs.push({ key, num, ref, li: matched.li, contentHtml });
  });

  if (!pairs.length) return;

  // 创建右侧边注栏（≥1100px 显示，与题记/延伸阅读同住批注栏）
  article.classList.add("article--has-sidenotes");
  const aside = document.createElement("aside");
  aside.className = "article-sidenotes";
  aside.setAttribute("aria-label", "边注");

  pairs.forEach((pair) => {
    const note = document.createElement("div");
    note.className = "sidenote";
    note.dataset.fnKey = pair.key;

    const numSpan = document.createElement("span");
    numSpan.className = "sidenote__num marker-sweep";
    numSpan.textContent = `[${pair.num}]`;

    const contentDiv = document.createElement("div");
    contentDiv.className = "sidenote__body";
    contentDiv.innerHTML = pair.contentHtml;

    note.appendChild(numSpan);
    note.appendChild(contentDiv);
    aside.appendChild(note);
    pair.sidenote = note;
    pair.numSpan = numSpan;
  });

  body.insertAdjacentElement("afterend", aside);
  tracked.push({
    element: aside,
    event: "click",
    type: "node",
    handler: () => article.classList.remove("article--has-sidenotes"),
  });

  // 计算 ≥1100px 下每条边注的纵向位置（与引用所在行顶对齐，重叠时向下顺延）
  const layoutSidenotes = () => {
    if (!window.matchMedia?.("(min-width: 1100px)").matches) {
      aside.style.minHeight = "";
      return;
    }
    const bodyRect = body.getBoundingClientRect();
    if (!bodyRect.height) return;

    let minNextTop = 0;
    pairs.forEach(({ ref, sidenote }) => {
      if (!sidenote) return;
      const refRect = ref.getBoundingClientRect();
      const desiredTop = Math.max(0, refRect.top - bodyRect.top - 2);
      const top = Math.max(desiredTop, minNextTop);
      sidenote.style.top = `${Math.round(top)}px`;
      minNextTop = top + sidenote.offsetHeight + 14;
    });
    aside.style.minHeight = `${Math.ceil(minNextTop)}px`;
  };

  // 初次排布 + 窗口尺寸变化或正文图片加载后重排
  window.requestAnimationFrame(layoutSidenotes);
  window.addEventListener("resize", layoutSidenotes);
  tracked.push({ element: window, event: "resize", handler: layoutSidenotes });

  body.querySelectorAll("img").forEach((img) => {
    img.addEventListener("load", layoutSidenotes);
    tracked.push({ element: img, event: "load", handler: layoutSidenotes });
  });

  // 交互：悬停/聚焦高亮对应边注；<1100px 点击就地展开/收起段后批注
  pairs.forEach((pair) => {
    const { ref, sidenote, numSpan, num, contentHtml } = pair;

    const activate = () => {
      sidenote?.classList.add("is-active");
      numSpan?.classList.add("is-on");
    };
    const deactivate = () => {
      sidenote?.classList.remove("is-active");
      numSpan?.classList.remove("is-on");
    };

    ref.addEventListener("mouseenter", activate);
    ref.addEventListener("mouseleave", deactivate);
    ref.addEventListener("focus", activate);
    ref.addEventListener("blur", deactivate);
    tracked.push({ element: ref, event: "mouseenter", handler: activate });
    tracked.push({ element: ref, event: "mouseleave", handler: deactivate });
    tracked.push({ element: ref, event: "focus", handler: activate });
    tracked.push({ element: ref, event: "blur", handler: deactivate });

    const clickHandler = (event) => {
      if (window.matchMedia?.("(min-width: 1100px)").matches) {
        event.preventDefault();
        activate();
        sidenote?.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return;
      }

      // <1100px：在当前段落下方就地展开/收起
      event.preventDefault();
      const hostBlock = ref.closest("p, li, blockquote, dd, td") || ref.parentElement;
      if (!hostBlock) return;

      if (pair.inlineEl && pair.inlineEl.isConnected) {
        pair.inlineEl.remove();
        pair.inlineEl = null;
        ref.setAttribute("aria-expanded", "false");
        return;
      }

      const inline = document.createElement("aside");
      inline.className = "footnote-inline";
      inline.setAttribute("role", "note");
      inline.innerHTML = `<span class="footnote-inline__num">[${num}]</span><div class="footnote-inline__body">${contentHtml}</div>`;
      hostBlock.insertAdjacentElement("afterend", inline);
      pair.inlineEl = inline;
      ref.setAttribute("aria-expanded", "true");
      tracked.push({ element: inline, event: "click", type: "node", handler: () => {} });
    };

    ref.addEventListener("click", clickHandler);
    tracked.push({ element: ref, event: "click", handler: clickHandler });
  });
}

/**
 * 为渲染后的文章正文挂载交互增强。
 * @returns {() => void} cleanup 撤销全部监听器与注入元素。
 */
export function enhanceArticleBody(body, headings = [], { openLightbox } = {}) {
  const tracked = [];
  enhanceExternalLinks(body, tracked);
  enhanceImages(body, tracked, openLightbox || (() => {}));
  enhanceCodeBlocks(body, tracked);
  enhanceHeadingAnchors(headings, tracked);
  enhanceFootnotes(body, tracked);

  return function cleanup() {
    tracked.forEach(({ element, event = "click", type, handler }) => {
      element.removeEventListener?.(event, handler);
      if (type === "button" || type === "node") {
        if (type === "node") handler?.();
        element.remove?.();
      }
    });
    tracked.length = 0;
  };
}
