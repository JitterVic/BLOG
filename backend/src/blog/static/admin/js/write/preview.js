// 预览模块：Markdown 实时预览、前台卡片预览与元信息联动。

import {
  categoryInput,
  coverImageInput,
  excerptInput,
  frontPreviewCover,
  frontPreviewExcerpt,
  frontPreviewMeta,
  frontPreviewQuote,
  frontPreviewTags,
  frontPreviewTitle,
  heroQuoteInput,
  markdownInput,
  previewMeta,
  previewTarget,
  publishedAtInput,
  readTimeInput,
  tagsInput,
  keywordsInput,
  titleInput,
} from "./dom.js";
import { fetchJson } from "./api.js";
import { highlightDeclared } from "../highlight.js";
import { setSaveState } from "./save-state.js";
import { escapeHtml, splitTags } from "./util.js";

let previewTimer = null;
let previewController = null;
let previewGeneration = 0;

// 保持对象引用稳定，其他模块读取同一对象即可获得最新值。
export const previewComputed = { excerpt: "", readTime: "1 min" };

export function highlightPreview() {
  if (!window.hljs || !previewTarget) return;
  previewTarget.querySelectorAll("pre code").forEach((code) => highlightDeclared(code));
}

export function renderPreviewMeta() {
  if (!previewMeta) return;
  const readTime = readTimeInput?.value.trim() || previewComputed.readTime || "1 min";
  const excerpt = excerptInput?.value.trim() || previewComputed.excerpt || "无自动摘要";
  previewMeta.textContent = `${readTime} \u00b7 ${excerpt}`;
}

export function updateFrontPreview() {
  if (!frontPreviewTitle) return;
  const title = titleInput?.value.trim() || "未命名文章";
  const category = categoryInput?.value.trim() || "Article";
  const publishedAt = publishedAtInput?.value.trim() || "未设置日期";
  const readTime = readTimeInput?.value.trim() || previewComputed.readTime || "1 min";
  const excerpt = excerptInput?.value.trim() || previewComputed.excerpt || "这篇文章暂时还没有摘要。";
  const quote = heroQuoteInput?.value.trim() || "";
  const cover = coverImageInput?.value.trim() || "";
  const tags = splitTags(tagsInput?.value || "");
  frontPreviewTitle.textContent = title;
  frontPreviewMeta.innerHTML = `<span>${escapeHtml(category)}</span><span>${escapeHtml(readTime)}</span><span>${escapeHtml(publishedAt)}</span>`;
  frontPreviewExcerpt.textContent = excerpt;
  frontPreviewQuote.textContent = quote;
  frontPreviewQuote.hidden = !quote;
  frontPreviewTags.innerHTML = tags.map((tag) => `<span>#${escapeHtml(tag)}</span>`).join("");
  if (cover) {
    frontPreviewCover.innerHTML = `<img src="${escapeHtml(cover)}" alt="" />`;
  } else {
    frontPreviewCover.textContent = "无封面图时，前台显示文字卡片。";
  }
}

async function requestPreview(generation) {
  if (!markdownInput || !previewTarget) return;
  if (previewController) previewController.abort();
  const controller = new AbortController();
  previewController = controller;
  try {
    if (previewMeta) previewMeta.textContent = "正在渲染……";
    const data = await fetchJson(document.body.dataset.previewUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({ markdown_content: markdownInput.value }),
    });
    if (generation !== previewGeneration || controller.signal.aborted) return;
    previewTarget.innerHTML = data.html || `<p>暂无预览内容</p>`;
    previewComputed.excerpt = data.excerpt || "";
    previewComputed.readTime = data.read_time || "1 min";
    renderPreviewMeta();
    highlightPreview();
    updateFrontPreview();
  } catch (error) {
    if (controller.signal.aborted || generation !== previewGeneration) return;
    if (previewMeta) previewMeta.textContent = error.message || "预览失败";
  } finally {
    if (previewController === controller) previewController = null;
  }
}

export function schedulePreview() {
  previewGeneration += 1;
  const generation = previewGeneration;
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(() => requestPreview(generation), 600);
}

function syncPreviewScroll() {
  if (!markdownInput || !previewTarget) return;
  const editorRange = Math.max(markdownInput.scrollHeight - markdownInput.clientHeight, 1);
  const previewRange = Math.max(previewTarget.scrollHeight - previewTarget.clientHeight, 0);
  previewTarget.scrollTop = (markdownInput.scrollTop / editorRange) * previewRange;
}

const metadataInputs = [titleInput, categoryInput, publishedAtInput, readTimeInput, excerptInput, tagsInput, keywordsInput, heroQuoteInput, coverImageInput];

export function initPreview() {
  metadataInputs.forEach((input) => input?.addEventListener("input", () => {
    updateFrontPreview();
    renderPreviewMeta();
    setSaveState("local");
  }));
  markdownInput?.addEventListener("input", () => {
    schedulePreview();
    setSaveState("local");
  });
  markdownInput?.addEventListener("scroll", syncPreviewScroll, { passive: true });

  highlightPreview();
  updateFrontPreview();
  schedulePreview();
}
