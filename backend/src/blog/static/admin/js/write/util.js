// 纯工具函数：转义、标签拆分、日期归一化。

export function escapeHtml(value = "") {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

export function splitTags(value = "") {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function normalizeDateInput(value = "") {
  const raw = String(value || "").trim();
  if (!raw) return "";
  const match = raw.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})/);
  if (!match) return "";
  return `${match[1]}-${match[2].padStart(2, "0")}-${match[3].padStart(2, "0")}`;
}

export function formatClock(value = Date.now()) {
  return new Date(value).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
