"use strict";

const adminPostSearch = document.getElementById("admin-post-search");
const adminPostStatus = document.getElementById("admin-post-status");
const adminPostCount = document.getElementById("admin-post-count");
const adminPostFilterEmpty = document.getElementById("admin-post-filter-empty");
const adminPostItems = Array.from(document.querySelectorAll("[data-post-item]"));
const profileForm = document.getElementById("profile-form");
const profileSaveStatus = document.getElementById("profile-save-status");
const profileSaveState = document.querySelector(".form-save-state");

function escapeAdminHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function updateAdminPostFilter() {
  if (!adminPostItems.length) return;
  const query = (adminPostSearch?.value || "").trim().toLowerCase();
  const status = adminPostStatus?.value || "";
  let visibleCount = 0;
  adminPostItems.forEach((item) => {
    const matchesQuery = !query || (item.dataset.search || "").includes(query);
    const matchesStatus = !status || item.dataset.status === status;
    const visible = matchesQuery && matchesStatus;
    item.hidden = !visible;
    if (visible) visibleCount += 1;
    else { const check = item.querySelector(".post-check"); if (check) check.checked = false; }
  });
  if (adminPostCount) {
    adminPostCount.textContent = query || status
      ? `\u663e\u793a ${visibleCount} / ${adminPostItems.length} \u7bc7\u7a3f\u4ef6`
      : `\u5171 ${adminPostItems.length} \u7bc7\u7a3f\u4ef6`;
  }
  if (adminPostFilterEmpty) adminPostFilterEmpty.hidden = visibleCount !== 0;
  updateBulkBar();
}

function markProfileDirty() {
  if (!profileForm || profileForm.dataset.submitting === "true") return;
  profileForm.dataset.dirty = "true";
  profileSaveState?.classList.remove("is-saved", "is-error");
  profileSaveState?.classList.add("is-dirty");
  if (profileSaveStatus) profileSaveStatus.textContent = "\u5c1a\u672a\u4fdd\u5b58\u7684\u4fee\u6539";
}

function bindLoadingForm(form) {
  form.addEventListener("invalid", (event) => {
    if (!form.dataset.invalidFocused) {
      form.dataset.invalidFocused = "true";
      event.target.focus();
      window.setTimeout(() => { delete form.dataset.invalidFocused; }, 0);
    }
  }, true);
  form.addEventListener("submit", (event) => {
    // If another capture-phase handler already cancelled submit (e.g. write-page
    // field validation), do not lock the form into a permanent loading state.
    if (event.defaultPrevented) return;
    const submitter = event.submitter || form.querySelector("button[type=submit]");
    const confirmation = submitter?.dataset.confirm || form.dataset.confirm;
    if (confirmation && !window.confirm(confirmation)) {
      event.preventDefault();
      return;
    }
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "true";
    form.classList.add("is-submitting");
    form.setAttribute("aria-busy", "true");
    // Defer disabling: a submit button disabled synchronously inside the submit
    // event is excluded when the browser serializes the form, dropping its
    // name/value pair (e.g. action=published on the write page).
    window.setTimeout(() => {
      form.querySelectorAll("button[type=submit]").forEach((button) => {
        button.disabled = true;
        if (button === submitter || button.dataset.loadingLabel) {
          button.dataset.originalLabel = button.textContent;
          button.textContent = button.dataset.loadingLabel || "\u5904\u7406\u4e2d\u2026";
        }
      });
    }, 0);
    if (form === profileForm) {
      profileForm.dataset.dirty = "false";
      if (profileSaveState) {
        profileSaveState.classList.remove("is-dirty", "is-saved", "is-error");
        profileSaveStatus.textContent = "\u6b63\u5728\u4fdd\u5b58\u2026";
      }
    }
  });
}

adminPostSearch?.addEventListener("input", updateAdminPostFilter);
adminPostStatus?.addEventListener("change", updateAdminPostFilter);

document.querySelectorAll("[data-loading-form]").forEach(bindLoadingForm);
document.querySelectorAll("[data-confirm-form]").forEach((form) => {
  const submit = form.querySelector("button[type=submit]");
  if (submit && form.dataset.confirm) submit.dataset.confirm = form.dataset.confirm;
});

document.querySelectorAll(".message").forEach((message) => {
  const timeout = message.classList.contains("error") ? 10000 : 7000;
  window.setTimeout(() => message.remove(), timeout);
});

const helpDialog = document.getElementById("admin-help-dialog");
document.getElementById("help-toggle")?.addEventListener("click", () => helpDialog?.showModal());
document.getElementById("help-close")?.addEventListener("click", () => helpDialog?.close());
helpDialog?.addEventListener("click", (event) => {
  if (event.target === helpDialog) helpDialog.close();
});

profileForm?.addEventListener("input", markProfileDirty);
profileForm?.addEventListener("change", markProfileDirty);

window.addEventListener("beforeunload", (event) => {
  if (profileForm?.dataset.dirty !== "true" || profileForm.dataset.submitting === "true") return;
  event.preventDefault();
  event.returnValue = "";
});

const profilePreviewButtons = document.querySelectorAll("[data-profile-preview]");
function updateProfilePreview() {
  if (!profileForm) return;
  const value = (name) => profileForm.elements.namedItem(name)?.value?.trim() || "";
  const set = (id, text) => { const node = document.getElementById(id); if (node) node.textContent = text; };
  set("profile-preview-name", value("name") || "站点名称");
  set("profile-preview-headline", value("headline") || value("name") || "首页主标题");
  set("profile-preview-summary", value("summary") || "首页导语会显示在这里。");
  const intro = document.getElementById("profile-preview-intro");
  if (intro) intro.innerHTML = (value("about_intro").split(/\r?\n/).map((line) => line.trim()).filter(Boolean).slice(0, 4).map((line) => `<p>${escapeAdminHtml(line)}</p>`).join("")) || "<p>\u5173\u4e8e\u9875\u7b80\u4ecb\u4f1a\u663e\u793a\u5728\u8fd9\u91cc\u3002</p>";
}
profilePreviewButtons.forEach((button) => button.addEventListener("click", () => {
  profilePreviewButtons.forEach((item) => item.classList.toggle("is-active", item === button));
  const mode = button.dataset.profilePreview;
  const home = document.getElementById("profile-preview-home");
  const about = document.getElementById("profile-preview-about");
  if (home) home.hidden = mode !== "home";
  if (about) about.hidden = mode !== "about";
}));
profileForm?.addEventListener("input", updateProfilePreview);
updateProfilePreview();

/* Dashboard: bulk selection, quick actions and client-side sorting */
const bulkForm = document.getElementById("bulk-form");
const bulkActionInput = document.getElementById("bulk-action");
const bulkCount = document.getElementById("bulk-count");
const bulkSelectAll = document.getElementById("bulk-select-all");
const postSort = document.getElementById("admin-post-sort");
const postList = document.getElementById("admin-post-list");

function visiblePostItems() {
  return adminPostItems.filter((item) => !item.hidden);
}

function checkedPostItems() {
  return visiblePostItems().filter((item) => item.querySelector(".post-check")?.checked);
}

function updateBulkBar() {
  if (!bulkForm) return;
  const checked = checkedPostItems();
  bulkForm.hidden = checked.length === 0;
  if (bulkCount) bulkCount.textContent = `已选 ${checked.length} 篇`;
  if (bulkSelectAll) {
    const visible = visiblePostItems();
    bulkSelectAll.checked = visible.length > 0 && checked.length === visible.length;
  }
}

bulkSelectAll?.addEventListener("change", () => {
  visiblePostItems().forEach((item) => {
    const check = item.querySelector(".post-check");
    if (check) check.checked = bulkSelectAll.checked;
  });
  updateBulkBar();
});

adminPostItems.forEach((item) => {
  item.querySelector(".post-check")?.addEventListener("change", updateBulkBar);
});

document.querySelectorAll("[data-bulk]").forEach((button) => {
  button.addEventListener("click", () => {
    if (!bulkForm || !bulkActionInput) return;
    if (!checkedPostItems().length) return;
    if (button.dataset.confirm && !window.confirm(button.dataset.confirm)) return;
    bulkActionInput.value = button.dataset.bulk;
    bulkForm.requestSubmit();
  });
});

function applyPostSort() {
  if (!postSort || !postList) return;
  const mode = postSort.value;
  const sorted = [...adminPostItems].sort((a, b) => {
    if (mode === "clicks") return (Number(b.dataset.sortClicks) || 0) - (Number(a.dataset.sortClicks) || 0);
    if (mode === "title") return (a.dataset.sortTitle || "").localeCompare(b.dataset.sortTitle || "", "zh-CN");
    if (mode === "published") return (b.dataset.sortPublished || "").localeCompare(a.dataset.sortPublished || "");
    return (b.dataset.sortUpdated || "").localeCompare(a.dataset.sortUpdated || "");
  });
  const emptyState = document.getElementById("admin-post-filter-empty");
  sorted.forEach((item) => postList.insertBefore(item, emptyState || null));
}

postSort?.addEventListener("change", applyPostSort);
updateAdminPostFilter();
updateBulkBar();