"use strict";

const adminPostSearch = document.getElementById("admin-post-search");
const adminPostStatus = document.getElementById("admin-post-status");
const adminPostCount = document.getElementById("admin-post-count");
const adminPostFilterEmpty = document.getElementById("admin-post-filter-empty");
const adminPostItems = Array.from(document.querySelectorAll("[data-post-item]"));
const profileForm = document.getElementById("profile-form");
const profileSaveStatus = document.getElementById("profile-save-status");
const profileSaveState = document.querySelector(".form-save-state");
const avatarInput = document.getElementById("avatar-input");
const avatarPreview = document.getElementById("avatar-preview");
const avatarFallback = document.getElementById("avatar-fallback");
const avatarFileName = document.getElementById("avatar-file-name");
const avatarDimensions = document.getElementById("avatar-dimensions");
let avatarObjectUrl = "";

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
    item.classList.toggle("is-hidden", !visible);
    if (visible) visibleCount += 1;
  });
  if (adminPostCount) {
    adminPostCount.textContent = query || status
      ? `\u663e\u793a ${visibleCount} / ${adminPostItems.length} \u7bc7\u7a3f\u4ef6`
      : `\u5171 ${adminPostItems.length} \u7bc7\u7a3f\u4ef6`;
  }
  if (adminPostFilterEmpty) adminPostFilterEmpty.hidden = visibleCount !== 0;
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
updateAdminPostFilter();

document.querySelectorAll("[data-loading-form]").forEach(bindLoadingForm);
document.querySelectorAll("[data-confirm-form]").forEach((form) => {
  const submit = form.querySelector("button[type=submit]");
  if (submit && form.dataset.confirm) submit.dataset.confirm = form.dataset.confirm;
});

document.querySelectorAll(".message").forEach((message) => {
  const timeout = message.classList.contains("error") ? 10000 : 7000;
  window.setTimeout(() => message.remove(), timeout);
});

profileForm?.addEventListener("input", markProfileDirty);
profileForm?.addEventListener("change", markProfileDirty);

avatarInput?.addEventListener("change", () => {
  const file = avatarInput.files?.[0];
  if (!file) {
    if (avatarFileName) avatarFileName.textContent = "\u5c1a\u672a\u9009\u62e9\u65b0\u5934\u50cf";
    return;
  }
  if (avatarFileName) avatarFileName.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
  if (!file.type.startsWith("image/") || !avatarPreview) return;
  if (avatarObjectUrl) URL.revokeObjectURL(avatarObjectUrl);
  avatarObjectUrl = URL.createObjectURL(file);
  avatarPreview.src = avatarObjectUrl;
  avatarPreview.hidden = false;
  avatarPreview.onload = () => {
    const width = avatarPreview.naturalWidth || 0;
    const height = avatarPreview.naturalHeight || 0;
    const ratio = width && height ? width / height : 1;
    if (avatarDimensions) {
      avatarDimensions.textContent = `${width} \u00d7 ${height} \u00b7 ${Math.abs(ratio - 1) < 0.08 ? "\u63a5\u8fd1 1:1\uff0c\u9002\u5408\u5934\u50cf\u88c1\u5207" : "\u524d\u53f0\u4f1a\u6309\u6b63\u65b9\u5f62\u5c45\u4e2d\u88c1\u5207"}`;
    }
  };
  if (avatarFallback) avatarFallback.hidden = true;
  markProfileDirty();
});

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
  const fallback = document.getElementById("avatar-fallback");
  if (fallback && !avatarInput?.files?.[0]) fallback.textContent = (value("name") || "A").slice(0, 1);
  set("profile-preview-name", value("name") || "站点名称");
  set("profile-preview-role", value("role"));
  set("profile-preview-location", value("location"));
  set("profile-preview-headline", value("headline") || value("name") || "首页主标题");
  set("profile-preview-summary", value("summary") || "首页导语会显示在这里。");
  set("profile-preview-note", value("hero_note") || "关于页题记");
  const intro = document.getElementById("profile-preview-intro");
  if (intro) intro.innerHTML = (value("about_intro").split(/\r?\n/).map((line) => line.trim()).filter(Boolean).slice(0, 4).map((line) => `<p>${escapeAdminHtml(line)}</p>`).join("")) || "<p>\u5173\u4e8e\u9875\u7b80\u4ecb\u4f1a\u663e\u793a\u5728\u8fd9\u91cc\u3002</p>";
  const calendar = document.getElementById("profile-preview-calendar");
  if (calendar) calendar.innerHTML = value("update_calendar").split(/\r?\n/).map((line) => line.split("|").map((item) => item.trim())).filter((parts) => parts[0] || parts[1]).slice(0, 3).map((parts) => `<span><time>${escapeAdminHtml(parts[0] || "\u2014")}</time>${escapeAdminHtml(parts[1] || "\u672a\u547d\u540d\u4e8b\u4ef6")}</span>`).join("");
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