// 媒体模块：图片上传、素材抽屉、粘贴与拖拽插入。

import {
  coverImageInput,
  drawerMediaCount,
  drawerMediaSearch,
  insertImageButton,
  markdownInput,
  mediaAltInput,
  mediaFileInput,
  mediaResult,
  uploadImageButton,
  workspace,
} from "./dom.js";
import { adminApiUrl, fetchJson } from "./api.js";
import { setSaveState } from "./save-state.js";
import { escapeHtml } from "./util.js";
import { dispatchEditorInput, insertBlock, replaceUploadPlaceholder } from "./editor.js";
import { closePanel } from "./panels.js";

let latestImageMarkdown = "";
let latestImageUrl = "";

export function renderMediaResult({ url = "", message = "", isError = false } = {}) {
  if (!mediaResult) return;
  mediaResult.classList.toggle("is-error", isError);
  mediaResult.classList.toggle("is-success", Boolean(url) && !isError);
  if (!url) {
    mediaResult.innerHTML = `<div class="result-copy">${escapeHtml(message)}</div>`;
    return;
  }
  latestImageUrl = url;
  const alt = mediaAltInput?.value.trim() || "image";
  latestImageMarkdown = `![${alt}](${url})`;
  mediaResult.innerHTML = `<img src="${escapeHtml(url)}" alt="" /><div class="copy-row"><code>${escapeHtml(url)}</code><button type="button" data-set-cover="${escapeHtml(url)}">设为封面</button></div>`;
}

function safeImageAlt(file) {
  return (file.name || "image").replace(/\.[^.]+$/, "").replace(/[\[\]()]/g, "-") || "image";
}

export async function uploadAndInsertImage(file) {
  if (!file?.type?.startsWith("image/") || !markdownInput) return;
  const token = `uploading-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const placeholder = `![上传中：${safeImageAlt(file)}](uploading://${token})`;
  const start = markdownInput.selectionStart;
  const end = markdownInput.selectionEnd;
  const scrollTop = markdownInput.scrollTop;
  markdownInput.setRangeText(placeholder, start, end, "end");
  markdownInput.scrollTop = scrollTop;
  markdownInput.focus();
  markdownInput.setSelectionRange(start + placeholder.length, start + placeholder.length);
  dispatchEditorInput();
  const anchor = { start, placeholder };
  setSaveState("syncing", `正在上传 ${file.name || "image"}……`);
  const formData = new FormData();
  formData.append("image", file);
  try {
    const data = await fetchJson(document.body.dataset.uploadUrl, { method: "POST", body: formData });
    const markdown = `![${safeImageAlt(file)}](${data.url})`;
    replaceUploadPlaceholder(anchor, markdown);
    latestImageMarkdown = markdown;
    renderMediaResult({ url: data.url });
    await refreshMediaDrawer();
    setSaveState("local");
  } catch (error) {
    replaceUploadPlaceholder(anchor, "");
    setSaveState("error", error.message || "图片上传失败");
  }
}

function mediaAssetCard(asset) {
  const name = asset.original_filename || asset.filename || "image";
  const dimensions = asset.width && asset.height ? `${asset.width} × ${asset.height} · ` : "";
  return `
    <article class="drawer-media-card" data-drawer-media data-search="${escapeHtml(`${name} ${asset.filename || ""} ${(asset.references || []).map((ref) => ref.title || "").join(" ")}`.toLowerCase())}">
      <img src="${escapeHtml(asset.url)}" alt="${escapeHtml(name)}" loading="lazy" />
      <div><strong title="${escapeHtml(name)}">${escapeHtml(name)}</strong><small>${escapeHtml(dimensions)}${Number(asset.reference_count || 0)} 处引用 · ${(Number(asset.size || 0) / 1024).toFixed(1)} KB</small></div>
      <div class="drawer-media-card__actions"><button type="button" data-insert-media="${escapeHtml(asset.url)}" data-media-name="${escapeHtml(name)}">插入</button><button type="button" data-set-cover="${escapeHtml(asset.url)}">设为封面</button></div>
    </article>`;
}

export async function refreshMediaDrawer() {
  const grid = document.getElementById("drawer-media-grid");
  if (!grid) return;
  try {
    const data = await fetchJson(adminApiUrl("media"));
    const items = data.items || [];
    grid.innerHTML = items.map(mediaAssetCard).join("");
    if (drawerMediaCount) drawerMediaCount.textContent = `${items.length} 张`;
    if (drawerMediaSearch) drawerMediaSearch.dispatchEvent(new Event("input"));
  } catch (error) {
    setSaveState("error", error.message || "媒体列表刷新失败");
  }
}

export function initMedia({ onDropMarkdownFile } = {}) {
  uploadImageButton?.addEventListener("click", async () => {
    const file = mediaFileInput?.files?.[0];
    if (!file) return renderMediaResult({ message: "请先选择图片文件。", isError: true });
    const formData = new FormData();
    formData.append("image", file);
    try {
      renderMediaResult({ message: "图片正在上传……" });
      const data = await fetchJson(document.body.dataset.uploadUrl, { method: "POST", body: formData });
      if (mediaAltInput && !mediaAltInput.value.trim()) {
        mediaAltInput.value = String(data.original_filename || file.name || "image").replace(/\.[^.]+$/, "");
      }
      renderMediaResult({ url: data.url });
      await refreshMediaDrawer();
    } catch (error) {
      renderMediaResult({ message: error.message || "上传失败", isError: true });
    }
  });

  mediaResult?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-set-cover]");
    if (!button || !coverImageInput) return;
    coverImageInput.value = button.dataset.setCover || "";
    coverImageInput.dispatchEvent(new Event("input", { bubbles: true }));
    button.textContent = "已设为封面";
  });

  insertImageButton?.addEventListener("click", () => {
    if (!latestImageUrl) return renderMediaResult({ message: "请先上传图片。", isError: true });
    const alt = mediaAltInput?.value.trim() || "image";
    latestImageMarkdown = `![${alt}](${latestImageUrl})`;
    insertBlock(latestImageMarkdown);
    closePanel("media-panel");
  });

  markdownInput?.addEventListener("paste", (event) => {
    const images = Array.from(event.clipboardData?.files || []).filter((file) => file.type.startsWith("image/"));
    if (!images.length) return;
    event.preventDefault();
    images.forEach((file) => uploadAndInsertImage(file));
  });

  workspace?.addEventListener("dragover", (event) => {
    if (!event.dataTransfer?.types?.includes("Files")) return;
    event.preventDefault();
    workspace.classList.add("is-dragover");
  });
  workspace?.addEventListener("dragleave", (event) => {
    if (!workspace.contains(event.relatedTarget)) workspace.classList.remove("is-dragover");
  });
  workspace?.addEventListener("drop", (event) => {
    const files = Array.from(event.dataTransfer?.files || []);
    if (!files.length) return;
    event.preventDefault();
    workspace.classList.remove("is-dragover");
    const markdownFile = files.find((file) => /\.(?:md|markdown|txt)$/i.test(file.name || ""));
    if (markdownFile) {
      onDropMarkdownFile?.(markdownFile);
      return;
    }
    files.filter((file) => file.type.startsWith("image/")).forEach((file) => uploadAndInsertImage(file));
  });

  drawerMediaSearch?.addEventListener("input", () => {
    const query = drawerMediaSearch.value.trim().toLowerCase();
    const cards = Array.from(document.querySelectorAll("[data-drawer-media]"));
    let visible = 0;
    cards.forEach((card) => {
      const show = !query || (card.dataset.search || "").includes(query);
      card.hidden = !show;
      if (show) visible += 1;
    });
    if (drawerMediaCount) drawerMediaCount.textContent = `${visible} 张`;
  });

  document.getElementById("drawer-media-grid")?.addEventListener("click", (event) => {
    const insert = event.target.closest("[data-insert-media]");
    if (insert) {
      const filename = insert.dataset.mediaName || "image";
      const fallbackAlt = filename.replace(/\.[^.]+$/, "").replace(/^[0-9-]+/, "") || "image";
      const alt = mediaAltInput?.value.trim() || fallbackAlt;
      insertBlock(`![${alt}](${insert.dataset.insertMedia})`);
      closePanel("media-panel");
      return;
    }
    const cover = event.target.closest("[data-set-cover]");
    if (cover && coverImageInput) {
      coverImageInput.value = cover.dataset.setCover || "";
      coverImageInput.dispatchEvent(new Event("input", { bubbles: true }));
      cover.textContent = "已设为封面";
    }
  });
}
