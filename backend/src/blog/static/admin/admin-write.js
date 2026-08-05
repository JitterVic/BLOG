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
const publishWarningsAcknowledged = document.getElementById("publish-warnings-acknowledged");
const revisionPanel = document.getElementById("revision-panel");
const revisionList = document.getElementById("revision-list");
const revisionCount = document.getElementById("revision-count");
const revisionPreview = document.getElementById("revision-preview");
const revisionPreviewType = document.getElementById("revision-preview-type");
const revisionPreviewTitle = document.getElementById("revision-preview-title");
const revisionPreviewTime = document.getElementById("revision-preview-time");
const revisionPreviewBody = document.getElementById("revision-preview-body");
const revisionRestore = document.getElementById("revision-restore");
const workingVersionInput = document.getElementById("working-copy-version");
const pendingBadge = document.getElementById("pending-badge");
const publishTrigger = document.querySelector(".publish-trigger");
const writingShell = document.querySelector(".writing-shell");
const writingStats = document.getElementById("writing-stats");
const outlineTarget = document.getElementById("writing-outline");
const drawerBackdrop = document.getElementById("drawer-backdrop");
const publishPanel = document.getElementById("publish-panel");
const publishCheckSummary = document.getElementById("publish-check-summary");
const publishCheckErrors = document.getElementById("publish-check-errors");
const publishCheckWarnings = document.getElementById("publish-check-warnings");
const publishConfirmButton = document.getElementById("publish-confirm-button");
const checkpointButton = document.getElementById("checkpoint-button");
const discardWorkingCopyButton = document.getElementById("discard-working-copy");
const mediaAltInput = document.getElementById("media-alt-text");
const drawerMediaSearch = document.getElementById("drawer-media-search");
const drawerMediaCount = document.getElementById("drawer-media-count");
const diffLeftSelect = document.getElementById("diff-left");
const diffRightSelect = document.getElementById("diff-right");
const compareVersionsButton = document.getElementById("compare-versions");
const generateSlugButton = document.getElementById("generate-slug-button");

let publishValidationPending = false;
let selectedRevisionId = null;
let pendingPublishSubmitter = null;
let panelReturnFocus = null;
let currentWorkingVersion = Number(postForm?.dataset.workingVersion || workingVersionInput?.value || 0) || null;

let previewTimer = null;
let previewController = null;
let previewGeneration = 0;
let previewComputed = { excerpt: "", readTime: "1 min" };
let latestImageMarkdown = "";
let latestImageUrl = "";

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
    const error = new Error(data.error || data.message || `\u8bf7\u6c42\u5931\uff1a${response.status}`);
    error.code = data.code || "request_failed";
    error.payload = data;
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
  latestImageUrl = url;
  const alt = mediaAltInput?.value.trim() || "image";
  latestImageMarkdown = `![${alt}](${url})`;
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
    if (mediaAltInput && !mediaAltInput.value.trim()) {
      mediaAltInput.value = String(data.original_filename || file.name || "image").replace(/\.[^.]+$/, "");
    }
    renderMediaResult({ url: data.url });
    await refreshMediaDrawer();
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
  if (!latestImageUrl) return renderMediaResult({ message: "\u8bf7\u5148\u4e0a\u4f20\u56fe\u7247\u3002", isError: true });
  const alt = mediaAltInput?.value.trim() || "image";
  latestImageMarkdown = `![${alt}](${latestImageUrl})`;
  insertBlock(latestImageMarkdown);
  closePanel("media-panel");
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

function saveLocalDraft({ announce = true, synced = false } = {}) {
  if (!postForm) return null;
  const payload = {
    savedAt: Date.now(),
    serverUpdatedAt: postForm.dataset.serverUpdatedAt || "",
    workingVersion: currentWorkingVersion,
    synced,
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
        expected_working_version: currentWorkingVersion,
        base_post_updated_at: postForm.dataset.basePostUpdatedAt || postForm.dataset.serverUpdatedAt || null,
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
    if (data.edit_source === "working_copy") {
      currentWorkingVersion = Number(data.working_version || 0) || null;
      postForm.dataset.workingVersion = String(currentWorkingVersion || "");
      postForm.dataset.basePostUpdatedAt = data.base_post_updated_at || postForm.dataset.basePostUpdatedAt || "";
      if (workingVersionInput) workingVersionInput.value = String(currentWorkingVersion || "");
      if (pendingBadge) pendingBadge.hidden = false;
      if (discardWorkingCopyButton) discardWorkingCopyButton.hidden = false;
      if (publishTrigger) { publishTrigger.disabled = false; publishTrigger.textContent = "\u53d1\u5e03\u66f4\u65b0"; }
    } else {
      postForm.dataset.serverUpdatedAt = data.updated_at || "";
    }
    if (draftRevision === requestRevision) {
      dirty = false;
      saveLocalDraft({ announce: false, synced: true });
      showRetryAutosave(false);
      setSaveState("server", data.edit_source === "working_copy"
        ? `\u5f85\u53d1\u5e03\u4fee\u6539\u5df2\u4fdd\u5b58 ${formatClock()}`
        : `\u5df2\u4fdd\u5b58\u5230\u670d\u52a1\u5668 ${formatClock()}`);
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
    } else if (!navigator.onLine || error.name === "TypeError") {
      autosaveConflict = false;
      saveLocalDraft({ announce: false });
      showRetryAutosave(true, false);
      setSaveState("local", "\u79bb\u7ebf\uff0c\u4fee\u6539\u5df2\u4fdd\u5b58\u5728\u672c\u5730");
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
  serverSaveTimer = window.setTimeout(persistDraftToServer, currentPostId() ? 2200 : 650);
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
  const sameServerVersion = Boolean(payload.serverUpdatedAt) && payload.serverUpdatedAt === (postForm?.dataset.serverUpdatedAt || "");
  const sameWorkingVersion = String(payload.workingVersion || "") === String(currentWorkingVersion || "");
  if (payload.synced === true || (sameServerVersion && sameWorkingVersion)) return;
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
    await refreshMediaDrawer();
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
  if (tip) tip.hidden = true;
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

function adminApiUrl(path) {
  const action = postForm?.getAttribute("action") || "/admin/posts/save";
  const base = action.replace(/\/posts\/save\/?$/, "");
  return `${base}/api/${path.replace(/^\//, "")}`;
}

function fieldForValidation(field) {
  if (field === "title") return titleInput;
  if (field === "slug") return slugInput;
  if (field === "excerpt") return excerptInput;
  if (field === "category") return categoryInput;
  if (field === "tags") return tagsInput;
  if (field === "cover_image") return coverImageInput;
  if (field === "markdown_content") return markdownInput;
  return null;
}

function publishFields() {
  const data = Object.fromEntries(new FormData(postForm).entries());
  delete data.csrf_token;
  delete data.action;
  delete data.publish_warnings_acknowledged;
  return data;
}

function renderPublishIssue(item, kind) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `publish-check-item is-${kind}`;
  button.dataset.validationField = item.field || "";
  button.innerHTML = `<strong>${escapeHtml(item.message || "")}</strong><small>${kind === "error" ? "\u5fc5\u987b\u4fee\u590d" : "\u8bf7\u786e\u8ba4\u540e\u7ee7\u7eed"}</small>`;
  return button;
}

function showPublishChecks({ errors = [], warnings = [] } = {}) {
  if (publishCheckErrors) {
    publishCheckErrors.innerHTML = "";
    errors.forEach((item) => publishCheckErrors.appendChild(renderPublishIssue(item, "error")));
  }
  if (publishCheckWarnings) {
    publishCheckWarnings.innerHTML = "";
    warnings.forEach((item) => publishCheckWarnings.appendChild(renderPublishIssue(item, "warning")));
  }
  if (publishCheckSummary) {
    publishCheckSummary.textContent = errors.length
      ? `\u53d1\u73b0 ${errors.length} \u4e2a\u5fc5\u987b\u4fee\u590d\u7684\u95ee\u9898\u3002`
      : warnings.length
        ? `\u6587\u7ae0\u53ef\u4ee5\u53d1\u5e03\uff0c\u53e6\u6709 ${warnings.length} \u6761\u63d0\u9192\u3002`
        : "\u68c0\u67e5\u5b8c\u6210\uff0c\u53ef\u4ee5\u53d1\u5e03\u3002";
  }
  if (publishConfirmButton) publishConfirmButton.hidden = errors.length > 0;
  openPanel("publish-panel");
}

async function runPublishPreflight(submitter) {
  if (publishValidationPending) return;
  publishValidationPending = true;
  pendingPublishSubmitter = submitter;
  setSaveState("working", "\u6b63\u5728\u68c0\u67e5\u53d1\u5e03\u5185\u5bb9\u2026\u2026");
  if (publishCheckSummary) publishCheckSummary.textContent = "\u6b63\u5728\u68c0\u67e5\u6587\u7ae0\u2026\u2026";
  if (publishCheckErrors) publishCheckErrors.innerHTML = "";
  if (publishCheckWarnings) publishCheckWarnings.innerHTML = "";
  if (publishConfirmButton) publishConfirmButton.hidden = true;
  openPanel("publish-panel");
  try {
    const result = await fetchJson(adminApiUrl("validate-post"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ post_id: currentPostId(), fields: publishFields() }),
    });
    showPublishChecks(result);
    setSaveState("server", "\u53d1\u5e03\u68c0\u67e5\u5b8c\u6210");
  } catch (error) {
    const errors = error.payload?.errors || [];
    const warnings = error.payload?.warnings || [];
    if (errors.length) {
      showPublishChecks({ errors, warnings });
      setSaveState("error", "\u53d1\u5e03\u524d\u8fd8\u6709\u5fc5\u987b\u4fee\u590d\u7684\u95ee\u9898");
    } else {
      if (publishCheckSummary) publishCheckSummary.textContent = error.message || "\u53d1\u5e03\u68c0\u67e5\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002";
      setSaveState("error", error.message || "\u53d1\u5e03\u68c0\u67e5\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002");
    }
  } finally {
    publishValidationPending = false;
  }
}

const REVISION_TYPE_LABELS = {
  created: "\u65b0\u5efa",
  draft_saved: "\u4fdd\u5b58\u8349\u7a3f",
  published: "\u53d1\u5e03",
  unpublished: "\u4e0b\u67b6",
  trashed: "\u79fb\u5165\u56de\u6536\u7ad9",
  restored_from_trash: "\u4ece\u56de\u6536\u7ad9\u6062\u590d",
  pre_restore: "\u6062\u590d\u524d\u5feb\u7167",
  restored: "\u6062\u590d\u5386\u53f2\u7248\u672c",
  checkpoint: "\u624b\u52a8\u4fdd\u5b58\u7248\u672c",
  discarded_changes: "\u4e22\u5f03\u7684\u4fee\u6539",
  restored_to_working_copy: "\u6062\u590d\u5230\u5f85\u53d1\u5e03\u4fee\u6539",
  pre_publish: "\u53d1\u5e03\u66f4\u65b0\u524d",
  pre_unpublish: "\u4e0b\u67b6\u524d",
  pre_trash: "\u79fb\u5165\u56de\u6536\u7ad9\u524d",
};

function formatRevisionTime(value) {
  const date = new Date(String(value || "").replace(" ", "T"));
  return Number.isNaN(date.getTime()) ? String(value || "") : date.toLocaleString("zh-CN");
}

function revisionStatusLabel(status) {
  if (status === "published") return "\u5df2\u53d1\u5e03";
  if (status === "trashed") return "\u56de\u6536\u7ad9";
  return "\u8349\u7a3f";
}

function renderRevisionList(items) {
  if (!revisionList) return;
  if (!items.length) {
    revisionList.innerHTML = '<p class="revision-empty">\u8fd8\u6ca1\u6709\u5386\u53f2\u7248\u672c\u3002\u624b\u52a8\u4fdd\u5b58\u6216\u53d1\u5e03\u540e\u4f1a\u51fa\u73b0\u5728\u8fd9\u91cc\u3002</p>';
    return;
  }
  revisionList.innerHTML = items.map((item) => `
    <button type="button" class="revision-item${item.id === selectedRevisionId ? " is-selected" : ""}" data-revision-id="${item.id}">
      <span class="revision-item__top"><strong>${escapeHtml(REVISION_TYPE_LABELS[item.revision_type] || item.revision_type)}</strong><small>${escapeHtml(revisionStatusLabel(item.status))}</small></span>
      <span class="revision-item__title">${escapeHtml(item.title || "\u65e0\u6807\u9898")}</span>
      <time datetime="${escapeHtml(item.created_at || "")}">${escapeHtml(formatRevisionTime(item.created_at))}</time>
    </button>
  `).join("");
}

async function loadRevisionDetail(revisionId) {
  const detail = await fetchJson(adminApiUrl(`posts/${postForm.dataset.postId}/revisions/${revisionId}`));
  selectedRevisionId = Number(revisionId);
  if (revisionPreview) revisionPreview.hidden = false;
  if (revisionPreviewType) revisionPreviewType.textContent = REVISION_TYPE_LABELS[detail.revision_type] || detail.revision_type;
  if (revisionPreviewTitle) revisionPreviewTitle.textContent = detail.snapshot?.title || "\u65e0\u6807\u9898";
  if (revisionPreviewTime) revisionPreviewTime.textContent = formatRevisionTime(detail.created_at);
  if (revisionPreviewBody) revisionPreviewBody.innerHTML = detail.snapshot?.html_content || "<p>\u8be5\u7248\u672c\u6ca1\u6709\u6b63\u6587\u3002</p>";
  if (revisionRestore) {
    revisionRestore.hidden = false;
    revisionRestore.dataset.revisionId = String(revisionId);
  }
  revisionList?.querySelectorAll("[data-revision-id]").forEach((button) => {
    button.classList.toggle("is-selected", Number(button.dataset.revisionId) === selectedRevisionId);
  });
}

async function loadRevisions() {
  if (!revisionPanel || !postForm?.dataset.postId) return;
  try {
    const result = await fetchJson(adminApiUrl(`posts/${postForm.dataset.postId}/revisions`));
    if (revisionCount) revisionCount.textContent = `${result.total || 0} \u4e2a\u7248\u672c`;
    renderRevisionList(result.items || []);
    populateDiffSelectors(result.items || []);
  } catch (error) {
    if (revisionList) revisionList.innerHTML = `<p class="revision-empty">${escapeHtml(error.message || "\u5386\u53f2\u7248\u672c\u52a0\u8f7d\u5931\u8d25")}</p>`;
    if (revisionCount) revisionCount.textContent = "\u52a0\u8f7d\u5931\u8d25";
  }
}

revisionList?.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-revision-id]");
  if (!button) return;
  try {
    await loadRevisionDetail(button.dataset.revisionId);
  } catch (error) {
    setSaveState("error", error.message || "\u5386\u53f2\u7248\u672c\u52a0\u8f7d\u5931\u8d25");
  }
});

revisionRestore?.addEventListener("click", async () => {
  const revisionId = revisionRestore.dataset.revisionId;
  const restoreMessage = postForm?.dataset.postStatus === "published"
    ? "\u6062\u590d\u540e\u4f1a\u751f\u6210\u5f85\u53d1\u5e03\u4fee\u6539\uff0c\u7ebf\u4e0a\u7248\u672c\u4fdd\u6301\u4e0d\u53d8\u3002\u786e\u5b9a\u7ee7\u7eed\u5417\uff1f"
    : "\u6062\u590d\u540e\u4f1a\u66ff\u6362\u5f53\u524d\u8349\u7a3f\uff0c\u5e76\u4fdd\u7559\u6062\u590d\u524d\u5feb\u7167\u3002\u786e\u5b9a\u7ee7\u7eed\u5417\uff1f";
  if (!revisionId || !window.confirm(restoreMessage)) return;
  revisionRestore.disabled = true;
  try {
    await fetchJson(adminApiUrl(`posts/${postForm.dataset.postId}/revisions/${revisionId}/restore`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    window.location.reload();
  } catch (error) {
    revisionRestore.disabled = false;
    setSaveState("error", error.message || "\u5386\u53f2\u7248\u672c\u6062\u590d\u5931\u8d25");
  }
});

loadRevisions();

function validatePostSubmission(event) {
  if (!postForm) return true;
  const action = event.submitter?.value || "draft";
  if (action === "published" && postForm.dataset.publishValidated !== "true") {
    runPublishPreflight(event.submitter);
    return false;
  }
  return true;
}

postForm?.addEventListener("invalid", (event) => {
  if (event.target === titleInput) setSaveState("error", "\u8bf7\u5148\u586b\u5199\u6587\u7ae0\u6807\u9898\u3002");
}, true);
postForm?.addEventListener("input", scheduleDraftPersistence);
postForm?.addEventListener("input", (event) => {
  event.target.removeAttribute?.("aria-invalid");
  postForm.dataset.publishValidated = "false";
  if (publishWarningsAcknowledged) publishWarningsAcknowledged.value = "0";
});
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

// Compact author workspace interactions.
function openPanel(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  if (panel.hidden && document.activeElement instanceof HTMLElement) panelReturnFocus = document.activeElement;
  document.querySelectorAll(".author-drawer:not([hidden])").forEach((item) => {
    if (item !== panel) item.hidden = true;
  });
  panel.hidden = false;
  if (drawerBackdrop) drawerBackdrop.hidden = false;
  const focusable = panel.querySelector("input, textarea, button, select, [tabindex]");
  window.setTimeout(() => focusable?.focus(), 0);
}

function closePanel(panelId, { restoreFocus = true } = {}) {
  const panel = document.getElementById(panelId);
  if (panel) panel.hidden = true;
  if (drawerBackdrop && !document.querySelector(".author-drawer:not([hidden])")) drawerBackdrop.hidden = true;
  if (restoreFocus && panelReturnFocus?.isConnected) window.setTimeout(() => panelReturnFocus.focus(), 0);
}

function closeAllPanels() {
  document.querySelectorAll(".author-drawer:not([hidden])").forEach((panel) => { panel.hidden = true; });
  if (drawerBackdrop) drawerBackdrop.hidden = true;
  if (panelReturnFocus?.isConnected) window.setTimeout(() => panelReturnFocus.focus(), 0);
}

document.addEventListener("click", (event) => {
  const toggle = event.target.closest("[data-toggle-panel]");
  if (toggle) {
    toggle.closest("details")?.removeAttribute("open");
    const panelId = toggle.dataset.togglePanel;
    const panel = document.getElementById(panelId);
    if (panel?.classList.contains("outline-panel")) panel.hidden = !panel.hidden;
    else openPanel(panelId);
    return;
  }
  const closer = event.target.closest("[data-close-panel]");
  if (closer) closePanel(closer.dataset.closePanel);
});
drawerBackdrop?.addEventListener("click", closeAllPanels);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") { closeAllPanels(); return; }
  if (event.key !== "Tab") return;
  const panel = document.querySelector(".author-drawer:not([hidden])");
  if (!panel) return;
  const focusable = Array.from(panel.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter((node) => !node.hidden);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});

function preferredViewMode() {
  const stored = localStorage.getItem("admin:write-view");
  if (stored && ["write", "split", "preview"].includes(stored)) return stored;
  if (window.matchMedia("(max-width: 760px)").matches) return "write";
  if (window.matchMedia("(max-width: 1179px)").matches) return "write";
  return "split";
}

function applyViewMode(mode) {
  if (!writingShell) return;
  let normalized = ["write", "split", "preview"].includes(mode) ? mode : "write";
  if (normalized === "split" && window.matchMedia("(max-width: 760px)").matches) normalized = "write";
  writingShell.dataset.view = normalized;
  localStorage.setItem("admin:write-view", normalized);
  document.querySelectorAll("[data-view-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewMode === normalized);
    button.setAttribute("aria-pressed", button.dataset.viewMode === normalized ? "true" : "false");
  });
}

document.querySelectorAll("[data-view-mode]").forEach((button) => {
  button.addEventListener("click", () => applyViewMode(button.dataset.viewMode));
});
applyViewMode(preferredViewMode());

document.getElementById("focus-mode-button")?.addEventListener("click", (event) => {
  const enabled = document.body.classList.toggle("is-focus-mode");
  event.currentTarget.textContent = enabled ? "退出专注" : "专注";
  if (enabled) applyViewMode("write");
});

function updateWritingAssist() {
  const markdown = markdownInput?.value || "";
  const compact = markdown.replace(/\s+/g, "");
  const readTime = previewComputed.readTime || "1 min";
  if (writingStats) writingStats.textContent = `${compact.length} 字 · ${readTime}`;
  if (!outlineTarget) return;
  const headings = [];
  let offset = 0;
  markdown.split(/\r?\n/).forEach((line) => {
    const match = line.match(/^(##|###)\s+(.+)/);
    if (match) headings.push({ level: match[1].length, text: match[2].trim(), offset });
    offset += line.length + 1;
  });
  if (!headings.length) {
    outlineTarget.innerHTML = "<p>添加二级标题后会在这里生成目录。</p>";
    return;
  }
  outlineTarget.innerHTML = headings.map((item, index) => `
    <button type="button" data-outline-index="${index}" data-level="${item.level}">${escapeHtml(item.text)}</button>
  `).join("");
  outlineTarget.querySelectorAll("[data-outline-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = headings[Number(button.dataset.outlineIndex)];
      if (!item || !markdownInput) return;
      markdownInput.focus();
      markdownInput.setSelectionRange(item.offset, item.offset);
      const before = markdown.slice(0, item.offset);
      const lineCount = before.split("\n").length;
      markdownInput.scrollTop = Math.max(0, (lineCount - 3) * 25);
      document.getElementById("outline-panel").hidden = true;
    });
  });
}

markdownInput?.addEventListener("input", updateWritingAssist);
updateWritingAssist();

postForm?.addEventListener("input", () => {
  if (postForm.dataset.postStatus === "published") {
    if (pendingBadge) pendingBadge.hidden = false;
    if (discardWorkingCopyButton) discardWorkingCopyButton.hidden = false;
    if (publishTrigger) { publishTrigger.disabled = false; publishTrigger.textContent = "发布更新"; }
  }
});

publishConfirmButton?.addEventListener("click", () => {
  if (!pendingPublishSubmitter || !postForm) return;
  if (publishWarningsAcknowledged) publishWarningsAcknowledged.value = "1";
  postForm.dataset.publishValidated = "true";
  closePanel("publish-panel");
  postForm.requestSubmit(pendingPublishSubmitter);
});

document.querySelectorAll(".publish-check-list").forEach((list) => {
  list.addEventListener("click", (event) => {
    const item = event.target.closest("[data-validation-field]");
    if (!item) return;
    const field = fieldForValidation(item.dataset.validationField);
    if (!field) return;
    if (field === markdownInput) {
      closePanel("publish-panel");
      applyViewMode("write");
    } else {
      openPanel("metadata-panel");
    }
    window.setTimeout(() => field.focus(), 50);
  });
});

checkpointButton?.addEventListener("click", async () => {
  const postId = currentPostId();
  if (!postId) return;
  checkpointButton.disabled = true;
  try {
    await persistDraftToServer();
    const result = await fetchJson(adminApiUrl(`posts/${postId}/checkpoint`), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    setSaveState("server", result.message || "已保存关键版本");
    await loadRevisions();
  } catch (error) {
    setSaveState("error", error.message || "保存版本失败");
  } finally {
    checkpointButton.disabled = false;
  }
});

discardWorkingCopyButton?.addEventListener("click", async () => {
  const postId = currentPostId();
  if (!postId || !window.confirm("确定丢弃待发布修改吗？系统会先保留一个可恢复版本。")) return;
  discardWorkingCopyButton.disabled = true;
  try {
    await fetchJson(adminApiUrl(`posts/${postId}/working-copy`), { method: "DELETE" });
    localStorage.removeItem(localDraftKey());
    window.location.reload();
  } catch (error) {
    discardWorkingCopyButton.disabled = false;
    setSaveState("error", error.message || "丢弃修改失败");
  }
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

document.addEventListener("keydown", (event) => {
  const modifier = event.ctrlKey || event.metaKey;
  if (!modifier) return;
  if (event.key.toLowerCase() === "s") {
    event.preventDefault();
    window.clearTimeout(localSaveTimer);
    window.clearTimeout(serverSaveTimer);
    saveLocalDraft({ announce: false });
    persistDraftToServer();
  }
  if (event.key === "Enter") {
    event.preventDefault();
    if (publishTrigger && !publishTrigger.disabled) postForm?.requestSubmit(publishTrigger);
  }
});

if (postForm?.dataset.postStatus === "published" && !postForm.dataset.workingVersion) {
  if (publishTrigger) { publishTrigger.disabled = true; publishTrigger.textContent = "已是最新"; }
}
function populateDiffSelectors(items = []) {
  if (!diffLeftSelect || !diffRightSelect) return;
  const leftValue = diffLeftSelect.value || "live";
  const rightValue = diffRightSelect.value || "working";
  const revisionOptions = items.map((item) =>
    `<option value="${item.id}">${escapeHtml(REVISION_TYPE_LABELS[item.revision_type] || item.revision_type)} \u00b7 ${escapeHtml(formatRevisionTime(item.created_at))}</option>`
  ).join("");
  diffLeftSelect.innerHTML = `<option value="live">\u7ebf\u4e0a/\u5f53\u524d\u7248\u672c</option>${revisionOptions}`;
  diffRightSelect.innerHTML = `<option value="working">\u5f53\u524d\u7f16\u8f91/\u5f85\u53d1\u5e03\u4fee\u6539</option>${revisionOptions}`;
  if (Array.from(diffLeftSelect.options).some((option) => option.value === leftValue)) diffLeftSelect.value = leftValue;
  if (Array.from(diffRightSelect.options).some((option) => option.value === rightValue)) diffRightSelect.value = rightValue;
}

function renderVersionDiff(result) {
  const target = document.getElementById("version-diff");
  if (!target) return;
  const fields = (result.field_changes || []).map((item) => `
    <div class="version-diff__field"><strong>${escapeHtml(item.field)}</strong><br><del>${escapeHtml(Array.isArray(item.before) ? item.before.join(", ") : item.before || "\uff08\u7a7a\uff09")}</del><br><ins>${escapeHtml(Array.isArray(item.after) ? item.after.join(", ") : item.after || "\uff08\u7a7a\uff09")}</ins></div>
  `).join("");
  const lines = (result.markdown_diff || []).map((line) => {
    const cls = line.startsWith("+") && !line.startsWith("+++") ? "diff-add" : line.startsWith("-") && !line.startsWith("---") ? "diff-remove" : "";
    return `<span class="${cls}">${escapeHtml(line)}</span>`;
  }).join("\n");
  target.hidden = false;
  target.innerHTML = result.changed
    ? `<div class="version-diff__fields">${fields}</div><pre>${lines || "\u6b63\u6587\u6ca1\u6709\u53d8\u5316"}</pre>`
    : "\u6240\u9009\u7248\u672c\u5185\u5bb9\u4e00\u81f4\u3002";
}

compareVersionsButton?.addEventListener("click", async () => {
  const target = document.getElementById("version-diff");
  const postId = currentPostId();
  if (!target || !postId) return;
  compareVersionsButton.disabled = true;
  target.hidden = false;
  target.textContent = "\u6b63\u5728\u6bd4\u8f83\u7248\u672c\u2026\u2026";
  try {
    if (dirty) await persistDraftToServer();
    const left = encodeURIComponent(diffLeftSelect?.value || "live");
    const right = encodeURIComponent(diffRightSelect?.value || "working");
    const result = await fetchJson(`${adminApiUrl(`posts/${postId}/diff`)}?left=${left}&right=${right}`);
    renderVersionDiff(result);
  } catch (error) {
    target.textContent = error.message || "\u7248\u672c\u6bd4\u8f83\u5931\u8d25";
  } finally {
    compareVersionsButton.disabled = false;
  }
});


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

async function refreshMediaDrawer() {
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

document.getElementById("tag-suggestions")?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-suggest-tag]");
  if (!button || !tagsInput) return;
  const values = splitTags(tagsInput.value || "");
  const tag = button.dataset.suggestTag || "";
  if (tag && !values.includes(tag)) values.push(tag);
  tagsInput.value = values.join(", ");
  tagsInput.dispatchEvent(new Event("input", { bubbles: true }));
});

generateSlugButton?.addEventListener("click", () => {
  if (!slugInput) return;
  const datePart = new Date().toISOString().slice(0, 10).replaceAll("-", "");
  const idPart = currentPostId() || Math.random().toString(36).slice(2, 8);
  slugInput.value = `post-${datePart}-${idPart}`;
  slugInput.dispatchEvent(new Event("input", { bubbles: true }));
  slugInput.focus();
});

window.addEventListener("offline", () => {
  saveLocalDraft({ announce: false });
  setSaveState("local", "离线，修改已保存在本地");
});
window.addEventListener("online", () => {
  if (!dirty) return;
  autosaveBlocked = false;
  setSaveState("syncing", "网络已恢复，正在同步……");
  persistDraftToServer();
});

if (!currentPostId() && !titleInput?.value.trim()) {
  window.setTimeout(() => titleInput?.focus(), 0);
}