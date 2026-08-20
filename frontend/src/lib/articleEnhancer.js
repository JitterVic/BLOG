// 文章正文 DOM 增强：外链安全、图片灯箱、代码复制按钮、标题锚点。
// 所有增强均可通过返回的 cleanup 函数完整撤销。

import hljs from "./highlight";

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
    hljs.highlightElement(code);
    pre.classList.add("has-code-toolbar");

    // 提取语言名称
    let lang = "";
    const langClass = Array.from(code.classList).find((c) => c.startsWith("language-") || c.startsWith("lang-"));
    if (langClass) {
      lang = langClass.replace(/^languages?-|^lang-/, "").toUpperCase();
    }
    if (!lang) {
      lang = pre.getAttribute("data-lang") || "CODE";
    }

    // 创建顶部工具条
    const toolbar = document.createElement("div");
    toolbar.className = "code-toolbar";

    const dots = document.createElement("div");
    dots.className = "code-toolbar__dots";
    dots.innerHTML = "<span></span><span></span><span></span>";

    const label = document.createElement("span");
    label.className = "code-toolbar__lang";
    label.textContent = lang;

    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "code-copy-button";
    copyBtn.innerHTML = `
      <svg class="copy-icon-svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
      </svg>
      <span class="copy-text">COPY</span>
    `;
    copyBtn.setAttribute("aria-label", "复制代码");

    const handler = async () => {
      try {
        await copyText(code.textContent || "");
        copyBtn.classList.add("copied");
        copyBtn.innerHTML = `
          <svg class="copy-icon-svg check-icon" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span class="copy-text">COPIED!</span>
        `;
      } catch {
        copyBtn.querySelector(".copy-text").textContent = "FAILED";
      }
      window.setTimeout(() => {
        copyBtn.classList.remove("copied");
        copyBtn.innerHTML = `
          <svg class="copy-icon-svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
          <span class="copy-text">COPY</span>
        `;
      }, 1800);
    };

    copyBtn.addEventListener("click", handler);
    toolbar.appendChild(dots);
    toolbar.appendChild(label);
    toolbar.appendChild(copyBtn);

    pre.insertBefore(toolbar, code);
    tracked.push({ element: copyBtn, type: "button", handler });
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
    tracked.push({ element: anchor, type: "button", handler });
  });
}

/**
 * 为渲染后的文章正文挂载交互增强。
 * @returns {() => void} cleanup 撤销全部监听器与注入元素。
 */
export function enhanceArticleBody(body, headings, { openLightbox } = {}) {
  const tracked = [];
  enhanceExternalLinks(body, tracked);
  enhanceImages(body, tracked, openLightbox || (() => {}));
  enhanceCodeBlocks(body, tracked);
  enhanceHeadingAnchors(headings, tracked);

  return function cleanup() {
    tracked.forEach(({ element, event = "click", type, handler }) => {
      element.removeEventListener(event, handler);
      if (type === "button") element.remove();
    });
    tracked.length = 0;
  };
}
