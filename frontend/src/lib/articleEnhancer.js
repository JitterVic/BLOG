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
    if (!code || pre.querySelector(".code-copy-button")) return;
    hljs.highlightElement(code);
    pre.classList.add("has-copy-button");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "code-copy-button";
    button.textContent = "COPY";
    button.setAttribute("aria-label", "复制代码");
    const handler = async () => {
      try {
        await copyText(code.textContent || "");
        button.textContent = "COPIED";
      } catch {
        button.textContent = "FAILED";
      }
      window.setTimeout(() => { button.textContent = "COPY"; }, 1200);
    };
    button.addEventListener("click", handler);
    pre.appendChild(button);
    tracked.push({ element: button, type: "button", handler });
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
