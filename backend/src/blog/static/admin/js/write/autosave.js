// 自动保存：本地草稿缓存、服务器同步、版本冲突与离线降级。

import {
  discardLocalDraftButton,
  postForm,
  postIdInput,
  publishWarningsAcknowledged,
  recoveryBanner,
  recoveryTime,
  restoreLocalDraftButton,
  retryAutosaveButton,
  titleInput,
} from "./dom.js";
import { fetchJson } from "./api.js";
import { setSaveState } from "./save-state.js";
import { formatClock } from "./util.js";
import { dispatchEditorInput } from "./editor.js";
import { updateFrontPreview } from "./preview.js";

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

export function currentPostId() {
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

export function saveLocalDraft({ announce = true, synced = false } = {}) {
  if (!postForm) return null;
  const payload = {
    savedAt: Date.now(),
    serverUpdatedAt: postForm.dataset.serverUpdatedAt || "",
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

export function showRetryAutosave(visible, conflict = false) {
  if (!retryAutosaveButton) return;
  retryAutosaveButton.hidden = !visible;
  retryAutosaveButton.dataset.mode = conflict ? "reload" : "retry";
  retryAutosaveButton.textContent = conflict ? "重新加载页面" : "重试同步";
}

export async function persistDraftToServer() {
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
    setSaveState("syncing", "正在自动保存……");
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
      document.title = "编辑文章 \u00b7 至知 Journal";
      const pageHeading = document.querySelector(".topbar-copy h1");
      if (pageHeading) pageHeading.textContent = "编辑文章";
      migrateLocalDraftKey(oldKey);
    }
    postForm.dataset.serverUpdatedAt = data.updated_at || "";
    if (draftRevision === requestRevision) {
      dirty = false;
      saveLocalDraft({ announce: false, synced: true });
      showRetryAutosave(false);
      setSaveState("server", `已保存到服务器 ${formatClock()}`);
    } else {
      dirty = true;
      serverSaveQueued = true;
      setSaveState("local", "已保存上一版，正在等待最新修改同步");
    }
  } catch (error) {
    if (error.name === "AbortError" && isSubmitting) return;
    if (error.code === "version_conflict") {
      autosaveBlocked = true;
      autosaveConflict = true;
      serverSaveQueued = false;
      showRetryAutosave(true, true);
      setSaveState("error", "服务器已有更新，请重新加载后再继续编辑");
    } else if (!navigator.onLine || error.name === "TypeError") {
      autosaveConflict = false;
      saveLocalDraft({ announce: false });
      showRetryAutosave(true, false);
      setSaveState("local", "离线，修改已保存在本地");
    } else {
      autosaveConflict = false;
      showRetryAutosave(true, false);
      setSaveState("error", error.message || "自动保存失败");
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

export function scheduleDraftPersistence() {
  if (!postForm || isSubmitting) return;
  dirty = true;
  draftRevision += 1;
  window.clearTimeout(localSaveTimer);
  window.clearTimeout(serverSaveTimer);
  localSaveTimer = window.setTimeout(() => saveLocalDraft(), 350);
  serverSaveTimer = window.setTimeout(persistDraftToServer, currentPostId() ? 2200 : 650);
}

export function cancelPendingSaveTimers() {
  window.clearTimeout(localSaveTimer);
  window.clearTimeout(serverSaveTimer);
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
  setSaveState("local", "已恢复本地草稿");
}

export function offerLocalDraftRecovery() {
  const payload = readLocalDraft();
  if (!payload?.savedAt || !recoveryBanner) return;
  const serverTime = Date.parse(postForm?.dataset.serverUpdatedAt || "") || 0;
  const sameServerVersion = Boolean(payload.serverUpdatedAt) && payload.serverUpdatedAt === (postForm?.dataset.serverUpdatedAt || "");
  if (payload.synced === true || sameServerVersion) return;
  const shouldOffer = !currentPostId() || payload.savedAt > serverTime;
  if (!shouldOffer) return;
  recoveryTime.textContent = `本地保存于 ${new Date(payload.savedAt).toLocaleString("zh-CN")}`;
  recoveryBanner.hidden = false;
  restoreLocalDraftButton.onclick = () => restoreDraft(payload);
  discardLocalDraftButton.onclick = () => {
    localStorage.removeItem(localDraftKey());
    recoveryBanner.hidden = true;
    setSaveState("local", "已放弃本地草稿");
  };
}

export function clearSavedLocalDraft() {
  if (!postForm || postForm.dataset.formSaved !== "true") return;
  localStorage.removeItem(localDraftKey());
  localStorage.removeItem("draft:new");
  postForm.dataset.formSaved = "false";
}

export function initAutosave() {
  retryAutosaveButton?.addEventListener("click", () => {
    if (autosaveConflict) {
      window.location.reload();
      return;
    }
    autosaveBlocked = false;
    showRetryAutosave(false);
    setSaveState("syncing", "正在重试同步……");
    persistDraftToServer();
  });

  postForm?.addEventListener("invalid", (event) => {
    if (event.target === titleInput) setSaveState("error", "请先填写文章标题。");
  }, true);
  postForm?.addEventListener("input", scheduleDraftPersistence);
  postForm?.addEventListener("input", (event) => {
    event.target.removeAttribute?.("aria-invalid");
    postForm.dataset.publishValidated = "false";
    if (publishWarningsAcknowledged) publishWarningsAcknowledged.value = "0";
  });
  postForm?.addEventListener("submit", () => setSaveState("syncing", "正在保存……"));
  postForm?.addEventListener("submit", () => {
    isSubmitting = true;
    dirty = false;
    serverSaveController?.abort();
    cancelPendingSaveTimers();
    setSaveState("syncing", "正在保存……");
    saveLocalDraft({ announce: false });
  });

  window.addEventListener("beforeunload", (event) => {
    if (!dirty || isSubmitting) return;
    event.preventDefault();
    event.returnValue = "";
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
}
