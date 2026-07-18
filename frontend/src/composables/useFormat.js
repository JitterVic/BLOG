export function displayDate(value, fallback = "未设置日期") {
  return value || fallback;
}

export function shortDate(value) {
  if (!value) return "--.--";
  const [, month, day] = String(value).split("-");
  return month && day ? `${month}-${day}` : value;
}

export function formatClicks(count = 0) {
  return `${count || 0} 次阅读`;
}
