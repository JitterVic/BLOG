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
const importWarning = document.getElementById("import-warning");
const retryAutosaveButton = document.getElementById("retry-autosave");

let previewTimer = null;
let previewController = null;
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

const SAVE_STATE_LABELS = {
  pristine: "\u672a\u4fee\u6539",
  local: "\u672c\u5730\u5df2\u4fdd\u5b58",
  syncing: "\u6b63\u5728\u540c\u6b65",
  server: "\u670d\u52a1\u5668\u5df2\u4fdd\u5b58",
  error: "\u540c\u6b65\u5931\u8d25",
};
const SAVE_STATE_CLASSES = ["is-pristine", "is-local", "is-syncing", "is-server", "is-error", "is-working", "is-saved"];

function setSaveState(state, detail = "") {
  if (autosaveStatus) autosaveStatus.textContent = detail || SAVE_STATE_LABELS[state] || state;
  if (!saveState) return;
  saveState.classList.remove(...SAVE_STATE_CLASSES);
  const className = state === "working" ? "is-syncing" : state === "saved" ? "is-server" : `is-${state}`;
  saveState.classList.add(className);
}

async function fetchJson(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = (options.method || "GET").toUpperCase();
  const csrfToken = document.body?.dataset.csrfToken;
  if (method !== "GET" && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(url, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || data.message || `\u8bf7\u6c42\u5931\u8d25\uff1a${response.status}`);
    error.code = data.code || "request_failed";
    throw error;
  }
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
  if (previewController) previewController.abort();
  const controller = new AbortController();
  previewController = controller;
  try {
    if (previewMeta) previewMeta.textContent = "\u6b63\u5728\u6e32\u67d3\u2026\u2026";
    const data = await fetchJson(document.body.dataset.previewUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({ markdown_content: markdownInput.value }),
    });
    if (generation !== previewGeneration || controller.signal.aborted) return;
    previewTarget.innerHTML = data.html || `<p>\u6682\u65e0\u9884\u89c8\u5185\u5bb9</p>`;
    previewComputed = { excerpt: data.excerpt || "", readTime: data.read_time || "1 min" };
    if (previewMeta) previewMeta.textContent = `${data.read_time} \u00b7 ${data.excerpt || "\u65e0\u81ea\u52a8\u6458\u8981"}`;
    highlightPreview();
    updateFrontPreview();
  } catch (error) {
    if (controller.signal.aborted || generation !== previewGeneration) return;
    if (previewMeta) previewMeta.textContent = error.message || "\u9884\u89c8\u5931\u8d25";
  } finally {
    if (previewController === controller) previewController = null;
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

function showImportWarning(markdownContent = "") {
  if (!importWarning) return;
  const references = markdownContent.match(/!\[[^\]]*\]\((?:\.{1,2}\/)[^)]+\)/g) || [];
  importWarning.hidden = references.length === 0;
  importWarning.textContent = references.length
    ? `\u68c0\u6d4b\u5230 ${references.length} \u5f20\u672c\u5730\u56fe\u7247\u5f15\u7528\uff0c\u8bf7\u4e0a\u4f20\u66ff\u6362\u3002`
    : "";
}

async function importMarkdownFile(file) {
  if (!file) return;
  const importUrl = document.body?.dataset?.importUrl;
  if (!importUrl) {
    setSaveState("error", "导入地址不可用，请刷新页面后重试。");
    showImportStatus("导入地址不可用，请刷新页面后重试。", true);
    return;
  }
  if (!/\.(?:md|markdown|txt)$/i.test(file.name || "")) {
    const message = "请选择 .md / .markdown 文稿文件（也兼容 .txt）。";
    setSaveState("error", message);
    showImportStatus(message, true);
    return;
  }
  if (markdownInput?.value.trim() && !window.confirm("编辑器中已有正文，导入 Markdown 会覆盖现有内容。确定继续吗？")) {
    return;
  }
  const formData = new FormData();
  formData.append("markdown_file", file);
  try {
    setSaveState("syncing", `正在导入 ${file.name || "Markdown"}……`);
    showImportStatus(`正在导入 ${file.name || "Markdown"}……`, false);
    const data = await fetchJson(importUrl, { method: "POST", body: formData });
    if (markdownInput) markdownInput.value = data.markdown_content || "";
    if (titleInput) titleInput.value = data.title || "";
    if (slugInput) {
      slugInput.value = data.slug || "";
      updateSlugHint();
    }
    if (categoryInput) categoryInput.value = data.category || "";
    if (publishedAtInput) publishedAtInput.value = normalizeDateInput(data.published_at || "");
    if (tagsInput) {
      tagsInput.value = data.tags_text || (Array.isArray(data.tags) ? data.tags.join(", ") : "");
    }
    if (excerptInput) excerptInput.value = data.excerpt || "";
    if (readTimeInput) readTimeInput.value = data.read_time || "";
    if (heroQuoteInput) heroQuoteInput.value = data.hero_quote || "";
    if (coverImageInput) coverImageInput.value = data.cover_image || "";
    showImportWarning(markdownInput?.value || "");
    showImportStatus(`已导入 ${file.name || "Markdown"}。若封面是相对路径，请改为 /uploads/ 或 http(s) 地址后再发布。`, false);
    dispatchEditorInput();
    updateFrontPreview();
    saveLocalDraft({ announce: false });
    scheduleDraftPersistence();
    setSaveState("local", "文稿已导入到编辑器（尚未发布）");
  } catch (error) {
    const message = error.message || "导入失败";
    setSaveState("error", message);
    showImportStatus(message, true);
    showRetryAutosave(false);
  }
}

function normalizeDateInput(value = "") {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const match = raw.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
  if (!match) return "";
  return `${match[1]}-${match[2].padStart(2, "0")}-${match[3].padStart(2, "0")}`;
}

function showImportStatus(message = "", isError = false) {
  if (!importWarning) return;
  if (!message) {
    importWarning.hidden = true;
    importWarning.textContent = "";
    importWarning.classList.remove("is-error", "is-success");
    return;
  }
  importWarning.hidden = false;
  importWarning.textContent = message;
  importWarning.classList.toggle("is-error", isError);
  importWarning.classList.toggle("is-success", !isError);
}

markdownFileInput?.addEventListener("change", async (event) => {
  const file = event.target.files?.[0];
  await importMarkdownFile(file);
  event.target.value = "";
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
  setSaveState("local");
}));
markdownInput?.addEventListener("input", () => {
  schedulePreview();
  setSaveState("local");
});
postForm?.addEventListener("submit", () => setSaveState("syncing", "\u6b63\u5728\u4fdd\u5b58\u2026\u2026"));

highlightPreview();
updateFrontPreview();
schedulePreview();


const postIdInput = document.getElementById("post-id");
const recoveryBanner = document.getElementById("draft-recovery-banner");
const recoveryTime = document.getElementById("draft-recovery-time");
const restoreLocalDraftButton = document.getElementById("restore-local-draft");
const discardLocalDraftButton = document.getElementById("discard-local-draft");
let localSaveTimer = null;
let serverSaveTimer = null;
let dirty = false;
let isSubmitting = false;
let draftRevision = 0;
let serverSaveInFlight = false;
let serverSaveController = null;
let serverSaveQueued = false;
let autosaveBlocked = false;
let autosaveConflict = false;

function currentPostId() {
  return String(postIdInput?.value || postForm?.dataset.postId || "").trim();
}

function localDraftKey() {
  return `draft:${currentPostId() || "new"}`;
}

function collectDraftFields() {
  if (!postForm) return {};
  const fields = {};
  const formData = new FormData(postForm);
  formData.forEach((value, key) => {
    if (typeof value === "string") fields[key] = value;
  });
  return fields;
}

function readLocalDraft(key = localDraftKey()) {
  try {
    return JSON.parse(localStorage.getItem(key) || "null");
  } catch {
    localStorage.removeItem(key);
    return null;
  }
}

function saveLocalDraft({ announce = true } = {}) {
  if (!postForm) return null;
  const payload = {
    savedAt: Date.now(),
    serverUpdatedAt: postForm.dataset.serverUpdatedAt || "",
    fields: collectDraftFields(),
  };
  localStorage.setItem(localDraftKey(), JSON.stringify(payload));
  if (announce) setSaveState("local");
  return payload;
}

function migrateLocalDraftKey(oldKey) {
  const nextKey = localDraftKey();
  if (oldKey === nextKey) return;
  const payload = localStorage.getItem(oldKey);
  if (payload) localStorage.setItem(nextKey, payload);
  localStorage.removeItem(oldKey);
}

function formatClock(value = Date.now()) {
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function showRetryAutosave(visible, conflict = false) {
  if (!retryAutosaveButton) return;
  retryAutosaveButton.hidden = !visible;
  retryAutosaveButton.dataset.mode = conflict ? "reload" : "retry";
  retryAutosaveButton.textContent = conflict ? "\u91cd\u65b0\u52a0\u8f7d\u9875\u9762" : "\u91cd\u8bd5\u540c\u6b65";
}

async function persistDraftToServer() {
  if (!postForm || isSubmitting || autosaveBlocked) return;
  if (serverSaveInFlight) {
    serverSaveQueued = true;
    return;
  }
  const status = postForm.dataset.postStatus || "draft";
  if (status === "published") {
    setSaveState("local", "\u5df2\u53d1\u5e03\u6587\u7ae0\uff1a\u4ec5\u672c\u5730\u81ea\u52a8\u4fdd\u5b58");
    return;
  }
  if (!titleInput?.value.trim()) {
    setSaveState("local", "\u586b\u5199\u6807\u9898\u540e\u5c06\u81ea\u52a8\u4fdd\u5b58\u5230\u670d\u52a1\u5668");
    return;
  }

  const oldKey = localDraftKey();
  const requestRevision = draftRevision;
  const requestFields = collectDraftFields();
  serverSaveInFlight = true;
  serverSaveController = new AbortController();
  showRetryAutosave(false);
  try {
    setSaveState("syncing", "\u6b63\u5728\u81ea\u52a8\u4fdd\u5b58\u2026\u2026");
    const data = await fetchJson(document.body.dataset.autosaveUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: serverSaveController.signal,
      body: JSON.stringify({
        post_id: currentPostId() || null,
        updated_at: postForm.dataset.serverUpdatedAt || null,
        fields: requestFields,
      }),
    });
    if (!currentPostId() && data.id) {
      postIdInput.value = String(data.id);
      postForm.dataset.postId = String(data.id);
      postForm.dataset.postStatus = "draft";
      const basePath = window.location.pathname.replace(/\/write(?:\/\d+)?$/, "/write");
      history.replaceState(null, "", `${basePath}/${data.id}`);
      document.title = "\u7f16\u8f91\u6587\u7ae0 \u00b7 \u81f3\u77e5 Journal";
      const pageHeading = document.querySelector(".topbar-copy h1");
      if (pageHeading) pageHeading.textContent = "\u7f16\u8f91\u6587\u7ae0";
      migrateLocalDraftKey(oldKey);
    }
    postForm.dataset.serverUpdatedAt = data.updated_at || "";
    if (draftRevision === requestRevision) {
      dirty = false;
      saveLocalDraft({ announce: false });
      showRetryAutosave(false);
      setSaveState("server", `\u5df2\u81ea\u52a8\u4fdd\u5b58 ${formatClock()}`);
    } else {
      dirty = true;
      serverSaveQueued = true;
      setSaveState("local", "\u5df2\u4fdd\u5b58\u4e0a\u4e00\u7248\uff0c\u6b63\u5728\u7b49\u5f85\u6700\u65b0\u4fee\u6539\u540c\u6b65");
    }
  } catch (error) {
    if (error.name === "AbortError" && isSubmitting) return;
    if (error.code === "version_conflict") {
      autosaveBlocked = true;
      autosaveConflict = true;
      serverSaveQueued = false;
      showRetryAutosave(true, true);
      setSaveState("error", "\u670d\u52a1\u5668\u5df2\u6709\u66f4\u65b0\uff0c\u8bf7\u91cd\u65b0\u52a0\u8f7d\u540e\u518d\u7ee7\u7eed\u7f16\u8f91");
    } else {
      autosaveConflict = false;
      showRetryAutosave(true, false);
      setSaveState("error", error.message || "\u81ea\u52a8\u4fdd\u5b58\u5931\u8d25");
    }
  } finally {
    serverSaveInFlight = false;
    serverSaveController = null;
    if (serverSaveQueued && !isSubmitting) {
      serverSaveQueued = false;
      window.clearTimeout(serverSaveTimer);
      serverSaveTimer = window.setTimeout(persistDraftToServer, 250);
    }
  }
}

retryAutosaveButton?.addEventListener("click", () => {
  if (autosaveConflict) {
    window.location.reload();
    return;
  }
  autosaveBlocked = false;
  showRetryAutosave(false);
  setSaveState("syncing", "\u6b63\u5728\u91cd\u8bd5\u540c\u6b65\u2026\u2026");
  persistDraftToServer();
});

function scheduleDraftPersistence() {
  if (!postForm || isSubmitting) return;
  dirty = true;
  draftRevision += 1;
  window.clearTimeout(localSaveTimer);
  window.clearTimeout(serverSaveTimer);
  localSaveTimer = window.setTimeout(() => saveLocalDraft(), 350);
  serverSaveTimer = window.setTimeout(persistDraftToServer, 2200);
}

function restoreDraft(payload) {
  if (!payload?.fields || !postForm) return;
  Object.entries(payload.fields).forEach(([name, value]) => {
    if (name === "post_id") return;
    const field = postForm.elements.namedItem(name);
    if (!field || typeof value !== "string") return;
    field.value = value;
  });
  recoveryBanner.hidden = true;
  dirty = true;
  updateFrontPreview();
  dispatchEditorInput();
  scheduleDraftPersistence();
  setSaveState("local", "\u5df2\u6062\u590d\u672c\u5730\u8349\u7a3f");
}

function offerLocalDraftRecovery() {
  const payload = readLocalDraft();
  if (!payload?.savedAt || !recoveryBanner) return;
  const serverTime = Date.parse(postForm?.dataset.serverUpdatedAt || "") || 0;
  const shouldOffer = !currentPostId() || payload.savedAt > serverTime;
  if (!shouldOffer) return;
  recoveryTime.textContent = `\u672c\u5730\u4fdd\u5b58\u4e8e ${new Date(payload.savedAt).toLocaleString("zh-CN")}`;
  recoveryBanner.hidden = false;
  restoreLocalDraftButton.onclick = () => restoreDraft(payload);
  discardLocalDraftButton.onclick = () => {
    localStorage.removeItem(localDraftKey());
    recoveryBanner.hidden = true;
    setSaveState("local", "\u5df2\u4e22\u5f03\u672c\u5730\u8349\u7a3f");
  };
}

function safeImageAlt(file) {
  return (file.name || "image").replace(/\.[^.]+$/, "").replace(/[\[\]()]/g, "-") || "image";
}

function insertAtCursor(text) {
  if (!markdownInput) return;
  const start = markdownInput.selectionStart;
  const end = markdownInput.selectionEnd;
  markdownInput.setRangeText(text, start, end, "end");
  markdownInput.focus();
  dispatchEditorInput();
}

function replaceUploadPlaceholder(anchor, replacement) {
  if (!markdownInput) return;
  const scrollTop = markdownInput.scrollTop;
  let position = anchor.start;
  if (markdownInput.value.slice(position, position + anchor.placeholder.length) !== anchor.placeholder) {
    position = markdownInput.value.indexOf(anchor.placeholder);
  }
  if (position < 0) {
    position = Math.min(anchor.start, markdownInput.value.length);
    markdownInput.setRangeText(replacement, position, position, "end");
  } else {
    markdownInput.setRangeText(replacement, position, position + anchor.placeholder.length, "end");
  }
  markdownInput.scrollTop = scrollTop;
  markdownInput.focus();
  markdownInput.setSelectionRange(position + replacement.length, position + replacement.length);
  dispatchEditorInput();
}

async function uploadAndInsertImage(file) {
  if (!file?.type?.startsWith("image/") || !markdownInput) return;
  const token = `uploading-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const placeholder = `![\u4e0a\u4f20\u4e2d\uff1a${safeImageAlt(file)}](uploading://${token})`;
  const start = markdownInput.selectionStart;
  const end = markdownInput.selectionEnd;
  const scrollTop = markdownInput.scrollTop;
  markdownInput.setRangeText(placeholder, start, end, "end");
  markdownInput.scrollTop = scrollTop;
  markdownInput.focus();
  markdownInput.setSelectionRange(start + placeholder.length, start + placeholder.length);
  dispatchEditorInput();
  const anchor = { start, placeholder };
  setSaveState("syncing", `\u6b63\u5728\u4e0a\u4f20 ${file.name || "image"}\u2026\u2026`);
  const formData = new FormData();
  formData.append("image", file);
  try {
    const data = await fetchJson(document.body.dataset.uploadUrl, { method: "POST", body: formData });
    const markdown = `![${safeImageAlt(file)}](${data.url})`;
    replaceUploadPlaceholder(anchor, markdown);
    latestImageMarkdown = markdown;
    renderMediaResult({ url: data.url });
    setSaveState("local");
  } catch (error) {
    replaceUploadPlaceholder(anchor, "");
    setSaveState("error", error.message || "\u56fe\u7247\u4e0a\u4f20\u5931\u8d25");
  }
}

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
    importMarkdownFile(markdownFile);
    return;
  }
  files.filter((file) => file.type.startsWith("image/")).forEach((file) => uploadAndInsertImage(file));
});

function clearSavedLocalDraft() {
  if (!postForm || postForm.dataset.formSaved !== "true") return;
  localStorage.removeItem(localDraftKey());
  localStorage.removeItem("draft:new");
  postForm.dataset.formSaved = "false";
}

function isSafeCoverUrl(value) {
  if (!value) return true;
  return /^https?:\/\//i.test(value) || /^\/uploads\/(?:media|avatars)\/[^/?#]+$/.test(value);
}

function focusValidationError(field, message) {
  if (!field) return false;
  field.setAttribute("aria-invalid", "true");
  field.focus();
  setSaveState("error", message);
  return false;
}


function syncWriteStatusUI(status = "draft") {
  const badge = document.getElementById("write-status-badge");
  const label = document.getElementById("write-status-label");
  const tip = document.getElementById("published-autosave-tip");
  const normalized = status === "published" ? "published" : "draft";
  if (postForm) postForm.dataset.postStatus = normalized;
  if (badge) {
    badge.dataset.status = normalized;
    badge.classList.toggle("is-published", normalized === "published");
    badge.classList.toggle("is-draft", normalized !== "published");
    badge.textContent = normalized === "published" ? "已发布" : "草稿";
  }
  if (label) {
    label.textContent = normalized === "published"
      ? "当前线上版本已发布。修改后请再次点击「发布文章」才会更新前台。"
      : "当前为草稿，前台不可见。确认无误后请点击「发布文章」。";
  }
  if (tip) tip.hidden = normalized !== "published";
}

function updateSlugHint() {
  const hint = document.getElementById("slug-hint");
  if (!hint || !slugInput) return;
  const value = slugInput.value.trim();
  const hasNonAscii = /[^\x00-\x7F]/.test(value);
  hint.hidden = !(value && hasNonAscii);
}

function countUnclosedFences(markdown = "") {
  let open = 0;
  for (const line of String(markdown).split(/\r?\n/)) {
    if (/^\s*```/.test(line)) open += 1;
  }
  return open % 2 === 1;
}

function hasHeadingSpaceIssues(markdown = "") {
  return /(?:^|\n)#{1,6}[^#\s\n]/.test(String(markdown));
}

function hasSectionHeadings(markdown = "") {
  return /(?:^|\n)##\s+\S/.test(String(markdown));
}

function validatePostSubmission(event) {
  if (!postForm) return true;
  const title = titleInput?.value.trim() || "";
  const slug = slugInput?.value.trim() || "";
  const cover = coverImageInput?.value.trim() || "";
  const tags = splitTags(tagsInput?.value || "");
  const markdown = markdownInput?.value || "";
  const action = event.submitter?.value || "draft";
  if (!title) return focusValidationError(titleInput, "请先填写文章标题。");
  if (slug && /[\s/?#]/.test(slug)) return focusValidationError(slugInput, "Slug 不能包含空格、斜杠或查询字符。");
  if (!isSafeCoverUrl(cover)) return focusValidationError(coverImageInput, "封面图片必须是 /uploads/ 地址或 http(s) 图片链接。");
  if (tags.length > 40) return focusValidationError(tagsInput, "标签数量不能超过 40 个。");
  if (action === "published" && !markdown.trim()) return focusValidationError(markdownInput, "发布前请先填写正文。");
  if (action === "published" && countUnclosedFences(markdown)) {
    return focusValidationError(markdownInput, "检测到未闭合的 ``` 代码围栏，请先补全后再发布。");
  }
  if (action === "published" && hasHeadingSpaceIssues(markdown)) {
    return focusValidationError(markdownInput, "标题 # 后需要空格，例如 `## 章节名`。");
  }
  if (action === "published" && !hasSectionHeadings(markdown)) {
    const ok = window.confirm("正文还没有二级标题（## 章节名）。前台将不会显示目录侧栏。仍要发布吗？");
    if (!ok) return focusValidationError(markdownInput, "已取消发布。建议用 ## 章节名 组织正文。");
  }
  return true;
}

postForm?.addEventListener("invalid", (event) => {
  if (event.target === titleInput) setSaveState("error", "\u8bf7\u5148\u586b\u5199\u6587\u7ae0\u6807\u9898\u3002");
}, true);
postForm?.addEventListener("input", scheduleDraftPersistence);
postForm?.addEventListener("input", (event) => event.target.removeAttribute?.("aria-invalid"));
postForm?.addEventListener("submit", (event) => {
  if (!validatePostSubmission(event)) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
}, true);
postForm?.addEventListener("submit", () => {
  isSubmitting = true;
  dirty = false;
  serverSaveController?.abort();
  window.clearTimeout(localSaveTimer);
  window.clearTimeout(serverSaveTimer);
  setSaveState("syncing", "\u6b63\u5728\u4fdd\u5b58\u2026\u2026");
  saveLocalDraft({ announce: false });
});
window.addEventListener("beforeunload", (event) => {
  if (!dirty || isSubmitting) return;
  event.preventDefault();
  event.returnValue = "";
});

slugInput?.addEventListener("input", updateSlugHint);
updateSlugHint();
syncWriteStatusUI(postForm?.dataset.postStatus || "draft");
clearSavedLocalDraft();
offerLocalDraftRecovery();
