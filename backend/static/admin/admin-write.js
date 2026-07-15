"use strict";

const postForm = document.getElementById("post-form");
const markdownInput = document.getElementById("markdown_content");
const previewTarget = document.getElementById("preview-target");
const previewMeta = document.getElementById("preview-meta");
const markdownFileInput = document.getElementById("markdown-file");
const titleInput = document.getElementById("title");
const slugInput = document.getElementById("slug");
const excerptInput = document.getElementById("excerpt");
const readTimeInput = document.getElementById("read_time");
const categoryInput = document.querySelector('[name="category"]');
const publishedAtInput = document.querySelector('[name="published_at"]');
const tagsInput = document.querySelector('[name="tags"]');
const heroQuoteInput = document.querySelector('[name="hero_quote"]');
const coverImageInput = document.getElementById("cover_image");
const frontPreviewCover = document.getElementById("front-preview-cover");
const frontPreviewMeta = document.getElementById("front-preview-meta");
const frontPreviewTitle = document.getElementById("front-preview-title");
const frontPreviewExcerpt = document.getElementById("front-preview-excerpt");
const frontPreviewQuote = document.getElementById("front-preview-quote");
const frontPreviewTags = document.getElementById("front-preview-tags");
const workspace = document.getElementById("writing-workspace");
const workspaceDivider = document.getElementById("workspace-divider");
const saveState = document.querySelector(".write-save-state");
const autosaveStatus = document.getElementById("autosave-status");
const mediaFileInput = document.getElementById("media-file");
const uploadImageButton = document.getElementById("upload-image-button");
const insertImageButton = document.getElementById("insert-image-button");
const mediaResult = document.getElementById("media-result");
const toolbar = document.querySelector(".markdown-toolbar");

let previewTimer = null;
let previewGeneration = 0;
let previewComputed = { excerpt: "", readTime: "1 min" };
let latestImageMarkdown = "";

function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function splitTags(value = "") {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function setStatus(message, state = "working") {
  if (autosaveStatus) autosaveStatus.textContent = message;
  if (!saveState) return;
  saveState.classList.remove("is-working", "is-saved", "is-error");
  if (state) saveState.classList.add(`is-${state}`);
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.message || `\u8bf7\u6c42\u5931\u8d25\uff1a${response.status}`);
  return data;
}

function highlightPreview() {
  if (!window.hljs || !previewTarget) return;
  previewTarget.querySelectorAll("pre code").forEach((code) => window.hljs.highlightElement(code));
}

function updateFrontPreview() {
  if (!frontPreviewTitle) return;
  const title = titleInput?.value.trim() || "\u672a\u547d\u540d\u6587\u7ae0";
  const category = categoryInput?.value.trim() || "Article";
  const publishedAt = publishedAtInput?.value.trim() || "\u672a\u8bbe\u7f6e\u65e5\u671f";
  const readTime = readTimeInput?.value.trim() || previewComputed.readTime || "1 min";
  const excerpt = excerptInput?.value.trim() || previewComputed.excerpt || "\u8fd9\u7bc7\u6587\u7ae0\u6682\u65f6\u8fd8\u6ca1\u6709\u6458\u8981\u3002";
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
    frontPreviewCover.classList.add("has-image");
    frontPreviewCover.innerHTML = `<img src="${escapeHtml(cover)}" alt="" />`;
  } else {
    frontPreviewCover.classList.remove("has-image");
    frontPreviewCover.textContent = "\u65e0\u5c01\u9762\u56fe\u65f6\uff0c\u524d\u53f0\u663e\u793a\u6587\u5b57\u5361\u7247\u3002";
  }
}

async function requestPreview(generation) {
  if (!markdownInput || !previewTarget) return;
  try {
    if (previewMeta) previewMeta.textContent = "\u6b63\u5728\u6e32\u67d3\u2026\u2026";
    const data = await fetchJson(document.body.dataset.previewUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown_content: markdownInput.value }),
    });
    if (generation !== previewGeneration) return;
    previewTarget.innerHTML = data.html || `<p>\u6682\u65e0\u9884\u89c8\u5185\u5bb9</p>`;
    previewComputed = { excerpt: data.excerpt || "", readTime: data.read_time || "1 min" };
    if (previewMeta) previewMeta.textContent = `${data.read_time} \u00b7 ${data.excerpt || "\u65e0\u81ea\u52a8\u6458\u8981"}`;
    highlightPreview();
    updateFrontPreview();
  } catch (error) {
    if (generation !== previewGeneration) return;
    if (previewMeta) previewMeta.textContent = error.message || "\u9884\u89c8\u5931\u8d25";
    setStatus(error.message || "\u9884\u89c8\u5931\u8d25", "error");
  }
}

function schedulePreview() {
  previewGeneration += 1;
  const generation = previewGeneration;
  window.clearTimeout(previewTimer);
  previewTimer = window.setTimeout(() => requestPreview(generation), 600);
}

function dispatchEditorInput() {
  markdownInput?.dispatchEvent(new Event("input", { bubbles: true }));
}

function replaceSelection(before, after = before, placeholder = "") {
  if (!markdownInput) return;
  const start = markdownInput.selectionStart;
  const end = markdownInput.selectionEnd;
  const selected = markdownInput.value.slice(start, end) || placeholder;
  markdownInput.setRangeText(`${before}${selected}${after}`, start, end, "end");
  markdownInput.focus();
  const cursorStart = start + before.length;
  markdownInput.setSelectionRange(cursorStart, cursorStart + selected.length);
  dispatchEditorInput();
}

function prefixSelectedLines(prefix) {
  if (!markdownInput) return;
  const start = markdownInput.selectionStart;
  const end = markdownInput.selectionEnd;
  const lineStart = markdownInput.value.lastIndexOf("\n", start - 1) + 1;
  const nextBreak = markdownInput.value.indexOf("\n", end);
  const lineEnd = nextBreak === -1 ? markdownInput.value.length : nextBreak;
  const selected = markdownInput.value.slice(lineStart, lineEnd);
  const replacement = selected.split("\n").map((line) => `${prefix}${line}`).join("\n");
  markdownInput.setRangeText(replacement, lineStart, lineEnd, "select");
  markdownInput.focus();
  dispatchEditorInput();
}

function insertBlock(content) {
  if (!markdownInput) return;
  const start = markdownInput.selectionStart;
  const paddingBefore = start > 0 && !markdownInput.value.slice(0, start).endsWith("\n\n") ? "\n\n" : "";
  const paddingAfter = markdownInput.value.slice(markdownInput.selectionEnd).startsWith("\n") ? "" : "\n";
  markdownInput.setRangeText(`${paddingBefore}${content}${paddingAfter}`, start, markdownInput.selectionEnd, "end");
  markdownInput.focus();
  dispatchEditorInput();
}

function runCommand(command) {
  const commands = {
    bold: () => replaceSelection("**", "**", "\u7c97\u4f53\u6587\u5b57"),
    italic: () => replaceSelection("*", "*", "\u659c\u4f53\u6587\u5b57"),
    h2: () => prefixSelectedLines("## "),
    h3: () => prefixSelectedLines("### "),
    quote: () => prefixSelectedLines("> "),
    code: () => insertBlock("```text\n\u5728\u8fd9\u91cc\u8f93\u5165\u4ee3\u7801\n```"),
    link: () => replaceSelection("[", "](https://)", "\u94fe\u63a5\u6587\u5b57"),
    image: () => replaceSelection("![", "](/uploads/media/)", "alt"),
    table: () => insertBlock("| \u5217 1 | \u5217 2 |\n| --- | --- |\n| \u5185\u5bb9 | \u5185\u5bb9 |"),
  };
  commands[command]?.();
}

toolbar?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-command]");
  if (button) runCommand(button.dataset.command);
});

markdownInput?.addEventListener("keydown", (event) => {
  const modifier = event.ctrlKey || event.metaKey;
  if (modifier && ["b", "i", "k"].includes(event.key.toLowerCase())) {
    event.preventDefault();
    runCommand({ b: "bold", i: "italic", k: "link" }[event.key.toLowerCase()]);
    return;
  }
  if (event.key === "Tab") {
    event.preventDefault();
    if (markdownInput.selectionStart !== markdownInput.selectionEnd) prefixSelectedLines("  ");
    else replaceSelection("  ", "", "");
  }
});

function syncPreviewScroll() {
  if (!markdownInput || !previewTarget) return;
  const editorRange = Math.max(markdownInput.scrollHeight - markdownInput.clientHeight, 1);
  const previewRange = Math.max(previewTarget.scrollHeight - previewTarget.clientHeight, 0);
  previewTarget.scrollTop = (markdownInput.scrollTop / editorRange) * previewRange;
}
markdownInput?.addEventListener("scroll", syncPreviewScroll, { passive: true });

function applyWorkspaceRatio(ratio) {
  if (!workspace || window.matchMedia("(max-width: 980px)").matches) return;
  const clamped = Math.min(70, Math.max(30, Number(ratio) || 50));
  workspace.style.gridTemplateColumns = `${clamped}% 10px calc(${100 - clamped}% - 10px)`;
  localStorage.setItem("admin:write-ratio", String(clamped));
  workspaceDivider?.setAttribute("aria-valuenow", String(Math.round(clamped)));
}

applyWorkspaceRatio(localStorage.getItem("admin:write-ratio") || 50);
workspaceDivider?.addEventListener("pointerdown", (event) => {
  event.preventDefault();
  workspaceDivider.classList.add("is-dragging");
  workspaceDivider.setPointerCapture(event.pointerId);
});
workspaceDivider?.addEventListener("pointermove", (event) => {
  if (!workspaceDivider.hasPointerCapture(event.pointerId)) return;
  const bounds = workspace.getBoundingClientRect();
  applyWorkspaceRatio(((event.clientX - bounds.left) / bounds.width) * 100);
});
workspaceDivider?.addEventListener("pointerup", (event) => {
  workspaceDivider.classList.remove("is-dragging");
  if (workspaceDivider.hasPointerCapture(event.pointerId)) workspaceDivider.releasePointerCapture(event.pointerId);
});
workspaceDivider?.addEventListener("keydown", (event) => {
  if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
  event.preventDefault();
  const current = Number(localStorage.getItem("admin:write-ratio") || 50);
  applyWorkspaceRatio(current + (event.key === 'ArrowLeft' ? -2 : 2));
});

markdownFileInput?.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;
  const formData = new FormData();
  formData.append("markdown_file", file);
  try {
    setStatus("\u6b63\u5728\u5bfc\u5165 Markdown\u2026\u2026", "working");
    const data = await fetchJson(document.body.dataset.importUrl, { method: "POST", body: formData });
    markdownInput.value = data.markdown_content || "";
    titleInput.value = data.title || titleInput.value;
    slugInput.value = data.slug || slugInput.value;
    excerptInput.value = data.excerpt || excerptInput.value;
    readTimeInput.value = data.read_time || readTimeInput.value;
    dispatchEditorInput();
    updateFrontPreview();
    setStatus("Markdown \u5df2\u5bfc\u5165", "saved");
  } catch (error) {
    setStatus(error.message || "\u5bfc\u5165\u5931\u8d25", "error");
  } finally {
    event.target.value = "";
  }
});

function renderMediaResult({ url = "", message = "", isError = false } = {}) {
  if (!mediaResult) return;
  mediaResult.classList.toggle("is-error", isError);
  mediaResult.classList.toggle("is-success", Boolean(url) && !isError);
  if (!url) {
    mediaResult.innerHTML = `<div class="result-copy">${escapeHtml(message)}</div>`;
    return;
  }
  latestImageMarkdown = `![image](${url})`;
  mediaResult.innerHTML = `<img src="${escapeHtml(url)}" alt="" /><div class="copy-row"><code>${escapeHtml(url)}</code><button type="button" data-set-cover="${escapeHtml(url)}">\u8bbe\u4e3a\u5c01\u9762</button></div>`;
}

uploadImageButton?.addEventListener("click", async () => {
  const file = mediaFileInput?.files?.[0];
  if (!file) return renderMediaResult({ message: "\u8bf7\u5148\u9009\u62e9\u56fe\u7247\u6587\u4ef6\u3002", isError: true });
  const formData = new FormData();
  formData.append("image", file);
  try {
    renderMediaResult({ message: "\u56fe\u7247\u6b63\u5728\u4e0a\u4f20\u2026\u2026" });
    const data = await fetchJson(document.body.dataset.uploadUrl, { method: "POST", body: formData });
    renderMediaResult({ url: data.url });
  } catch (error) {
    renderMediaResult({ message: error.message || "\u4e0a\u4f20\u5931\u8d25", isError: true });
  }
});

mediaResult?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-set-cover]");
  if (!button || !coverImageInput) return;
  coverImageInput.value = button.dataset.setCover || "";
  coverImageInput.dispatchEvent(new Event("input", { bubbles: true }));
  button.textContent = "\u5df2\u8bbe\u4e3a\u5c01\u9762";
});

insertImageButton?.addEventListener("click", () => {
  if (!latestImageMarkdown) return renderMediaResult({ message: "\u8bf7\u5148\u4e0a\u4f20\u56fe\u7247\u3002", isError: true });
  insertBlock(latestImageMarkdown);
});

const metadataInputs = [titleInput, categoryInput, publishedAtInput, readTimeInput, excerptInput, tagsInput, heroQuoteInput, coverImageInput];
metadataInputs.forEach((input) => input?.addEventListener("input", () => {
  updateFrontPreview();
  setStatus("\u6709\u672a\u4fdd\u5b58\u4fee\u6539", "working");
}));
markdownInput?.addEventListener("input", () => {
  schedulePreview();
  setStatus("\u6b63\u5728\u7f16\u8f91\u2026\u2026", "working");
});
postForm?.addEventListener("submit", () => setStatus("\u6b63\u5728\u4fdd\u5b58\u2026\u2026", "working"));

highlightPreview();
updateFrontPreview();
schedulePreview();
