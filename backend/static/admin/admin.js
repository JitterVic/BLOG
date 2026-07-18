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
let avatarObjectUrl = "";

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
  if (avatarFallback) avatarFallback.hidden = true;
  markProfileDirty();
});

window.addEventListener("beforeunload", (event) => {
  if (profileForm?.dataset.dirty !== "true" || profileForm.dataset.submitting === "true") return;
  event.preventDefault();
  event.returnValue = "";
});
