// 发布模块：发布前校验、状态徽章、slug 提示与辅助输入。

import {
  categoryInput,
  coverImageInput,
  excerptInput,
  generateSlugButton,
  markdownInput,
  postForm,
  publishCheckErrors,
  publishCheckSummary,
  publishCheckWarnings,
  publishConfirmButton,
  publishWarningsAcknowledged,
  slugInput,
  tagsInput,
  titleInput,
} from "./dom.js";
import { adminApiUrl, fetchJson } from "./api.js";
import { setSaveState } from "./save-state.js";
import { escapeHtml, splitTags } from "./util.js";
import { openPanel, closePanel } from "./panels.js";
import { currentPostId, clearSavedLocalDraft, offerLocalDraftRecovery } from "./autosave.js";
import { applyViewMode } from "./workspace.js";

let publishValidationPending = false;
let pendingPublishSubmitter = null;

export function isSafeCoverUrl(value) {
  if (!value) return true;
  return /^https?:\/\//i.test(value) || /^\/uploads\/media\/[^/?#]+$/.test(value);
}

export function focusValidationError(field, message) {
  if (!field) return false;
  field.setAttribute("aria-invalid", "true");
  field.focus();
  setSaveState("error", message);
  return false;
}

export function syncWriteStatusUI(status = "draft") {
  const badge = document.getElementById("write-status-badge");
  const normalized = status === "published" ? "published" : "draft";
  if (postForm) postForm.dataset.postStatus = normalized;
  if (badge) {
    badge.dataset.status = normalized;
    badge.classList.toggle("is-published", normalized === "published");
    badge.classList.toggle("is-draft", normalized !== "published");
    badge.textContent = normalized === "published" ? "已发布" : "草稿";
  }
}

export function updateSlugHint() {
  const hint = document.getElementById("slug-hint");
  if (!hint || !slugInput) return;
  const value = slugInput.value.trim();
  const hasNonAscii = /[^\x00-\x7F]/.test(value);
  hint.hidden = !(value && hasNonAscii);
}

export function countUnclosedFences(markdown = "") {
  let open = 0;
  for (const line of String(markdown).split(/\r?\n/)) {
    if (/^\s*```/.test(line)) open += 1;
  }
  return open % 2 === 1;
}

export function hasHeadingSpaceIssues(markdown = "") {
  return /(?:^|\n)#{1,6}[^#\s\n]/.test(String(markdown));
}

export function hasSectionHeadings(markdown = "") {
  return /(?:^|\n)##\s+\S/.test(String(markdown));
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
  button.innerHTML = `<strong>${escapeHtml(item.message || "")}</strong><small>${kind === "error" ? "必须修复" : "请确认后继续"}</small>`;
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
      ? `发现 ${errors.length} 个必须修复的问题。`
      : warnings.length
        ? `文章可以发布，另有 ${warnings.length} 条提醒。`
        : "检查完成，可以发布。";
  }
  if (publishConfirmButton) publishConfirmButton.hidden = errors.length > 0;
  openPanel("publish-panel");
}

async function runPublishPreflight(submitter) {
  if (publishValidationPending) return;
  publishValidationPending = true;
  pendingPublishSubmitter = submitter;
  setSaveState("working", "正在检查发布内容……");
  if (publishCheckSummary) publishCheckSummary.textContent = "正在检查文章……";
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
    setSaveState("server", "发布检查完成");
  } catch (error) {
    const errors = error.payload?.errors || [];
    const warnings = error.payload?.warnings || [];
    if (errors.length) {
      showPublishChecks({ errors, warnings });
      setSaveState("error", "发布前还有必须修复的问题");
    } else {
      if (publishCheckSummary) publishCheckSummary.textContent = error.message || "发布检查失败，请稍后重试。";
      setSaveState("error", error.message || "发布检查失败，请稍后重试。");
    }
  } finally {
    publishValidationPending = false;
  }
}

export function validatePostSubmission(event) {
  if (!postForm) return true;
  const action = event.submitter?.value || "draft";
  if (action === "published" && postForm.dataset.publishValidated !== "true") {
    runPublishPreflight(event.submitter);
    return false;
  }
  return true;
}

export function initPublish() {
  postForm?.addEventListener("submit", (event) => {
    if (!validatePostSubmission(event)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  slugInput?.addEventListener("input", updateSlugHint);
  updateSlugHint();
  syncWriteStatusUI(postForm?.dataset.postStatus || "draft");
  clearSavedLocalDraft();
  offerLocalDraftRecovery();

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
}
