"use strict";

const adminPostSearch = document.getElementById("admin-post-search");
const adminPostStatus = document.getElementById("admin-post-status");
const adminPostCount = document.getElementById("admin-post-count");
const adminPostItems = Array.from(document.querySelectorAll("[data-post-item]"));

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
  });
  if (adminPostCount) {
    adminPostCount.textContent = query || status
      ? `\u663e\u793a ${visibleCount} / ${adminPostItems.length} \u7bc7\u7a3f\u4ef6`
      : `\u5171 ${adminPostItems.length} \u7bc7\u7a3f\u4ef6`;
  }
}

adminPostSearch?.addEventListener("input", updateAdminPostFilter);
adminPostStatus?.addEventListener("change", updateAdminPostFilter);
updateAdminPostFilter();
