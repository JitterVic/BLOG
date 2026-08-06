// 历史版本模块：版本列表、快照预览、恢复与手动检查点。

import {
  checkpointButton,
  postForm,
  revisionCount,
  revisionList,
  revisionPanel,
  revisionPreview,
  revisionPreviewBody,
  revisionPreviewTime,
  revisionPreviewTitle,
  revisionPreviewType,
  revisionRestore,
} from "./dom.js";
import { adminApiUrl, fetchJson } from "./api.js";
import { setSaveState } from "./save-state.js";
import { escapeHtml } from "./util.js";
import { currentPostId, persistDraftToServer } from "./autosave.js";

let selectedRevisionId = null;

const REVISION_TYPE_LABELS = {
  created: "新建",
  draft_saved: "保存草稿",
  published: "发布",
  unpublished: "下架",
  trashed: "移入回收站",
  restored_from_trash: "从回收站恢复",
  pre_restore: "恢复前快照",
  restored: "恢复历史版本",
  checkpoint: "手动保存版本",
  pre_publish: "发布更新前",
  pre_unpublish: "下架前",
  pre_trash: "移入回收站前",
};

function formatRevisionTime(value) {
  const date = new Date(String(value || "").replace(" ", "T"));
  return Number.isNaN(date.getTime()) ? String(value || "") : date.toLocaleString("zh-CN");
}

function revisionStatusLabel(status) {
  if (status === "published") return "已发布";
  if (status === "trashed") return "回收站";
  return "草稿";
}

function renderRevisionList(items) {
  if (!revisionList) return;
  if (!items.length) {
    revisionList.innerHTML = '<p class="revision-empty">还没有历史版本。手动保存或发布后会出现在这里。</p>';
    return;
  }
  revisionList.innerHTML = items.map((item) => `
    <button type="button" class="revision-item${item.id === selectedRevisionId ? " is-selected" : ""}" data-revision-id="${item.id}">
      <span class="revision-item__top"><strong>${escapeHtml(REVISION_TYPE_LABELS[item.revision_type] || item.revision_type)}</strong><small>${escapeHtml(revisionStatusLabel(item.status))}</small></span>
      <span class="revision-item__title">${escapeHtml(item.title || "无标题")}</span>
      <time datetime="${escapeHtml(item.created_at || "")}">${escapeHtml(formatRevisionTime(item.created_at))}</time>
    </button>
  `).join("");
}

async function loadRevisionDetail(revisionId) {
  const detail = await fetchJson(adminApiUrl(`posts/${postForm.dataset.postId}/revisions/${revisionId}`));
  selectedRevisionId = Number(revisionId);
  if (revisionPreview) revisionPreview.hidden = false;
  if (revisionPreviewType) revisionPreviewType.textContent = REVISION_TYPE_LABELS[detail.revision_type] || detail.revision_type;
  if (revisionPreviewTitle) revisionPreviewTitle.textContent = detail.snapshot?.title || "无标题";
  if (revisionPreviewTime) revisionPreviewTime.textContent = formatRevisionTime(detail.created_at);
  if (revisionPreviewBody) revisionPreviewBody.innerHTML = detail.snapshot?.html_content || "<p>该版本没有正文。</p>";
  if (revisionRestore) {
    revisionRestore.hidden = false;
    revisionRestore.dataset.revisionId = String(revisionId);
  }
  revisionList?.querySelectorAll("[data-revision-id]").forEach((button) => {
    button.classList.toggle("is-selected", Number(button.dataset.revisionId) === selectedRevisionId);
  });
}

export async function loadRevisions() {
  if (!revisionPanel || !postForm?.dataset.postId) return;
  try {
    const result = await fetchJson(adminApiUrl(`posts/${postForm.dataset.postId}/revisions`));
    if (revisionCount) revisionCount.textContent = `${result.total || 0} 个版本`;
    renderRevisionList(result.items || []);
  } catch (error) {
    if (revisionList) revisionList.innerHTML = `<p class="revision-empty">${escapeHtml(error.message || "历史版本加载失败")}</p>`;
    if (revisionCount) revisionCount.textContent = "加载失败";
  }
}

export function initRevisions() {
  revisionList?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-revision-id]");
    if (!button) return;
    try {
      await loadRevisionDetail(button.dataset.revisionId);
    } catch (error) {
      setSaveState("error", error.message || "历史版本加载失败");
    }
  });

  revisionRestore?.addEventListener("click", async () => {
    const revisionId = revisionRestore.dataset.revisionId;
    const restoreMessage = postForm?.dataset.postStatus === "published"
      ? "恢复后会直接更新线上版本，并保留恢复前快照。确定继续吗？"
      : "恢复后会替换当前草稿，并保留恢复前快照。确定继续吗？";
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
      setSaveState("error", error.message || "历史版本恢复失败");
    }
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

  loadRevisions();
}
