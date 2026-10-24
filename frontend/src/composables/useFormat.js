export function displayDate(value, fallback = "未设置日期") {
  return value || fallback;
}

/** 组内日期：MM-DD（年分组已经交代了年份）。 */
export function shortDate(value) {
  if (!value) return "--.--";
  const [, month, day] = String(value).split("-");
  return month && day ? `${month}-${day}` : value;
}

/** 阅读时长："8 min" → "约 8 分钟"。 */
export function readTimeLabel(value) {
  const match = String(value || "").match(/^\s*(\d+)\s*min/i);
  if (match) return `约 ${match[1]} 分钟`;
  return value || "";
}

/** 阅读数：千分位 + 单位（"1,204 次阅读"），调用处勿重复加「次」。 */
export function formatClicks(count = 0) {
  return `${Number(count || 0).toLocaleString("zh-CN")} 次阅读`;
}
