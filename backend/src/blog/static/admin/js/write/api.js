// 后台 API 请求封装：CSRF 头注入与错误归一化。

import { postForm } from "./dom.js";

export async function fetchJson(url, options = {}) {
  const headers = new Headers(options.headers || {});
  const method = (options.method || "GET").toUpperCase();
  const csrfToken = document.body?.dataset.csrfToken;
  if (method !== "GET" && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const response = await fetch(url, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || data.message || `请求失败：${response.status}`);
    error.code = data.code || "request_failed";
    error.payload = data;
    throw error;
  }
  return data;
}

export function adminApiUrl(path) {
  const action = postForm?.getAttribute("action") || "/admin/posts/save";
  const base = action.replace(/\/posts\/save\/?$/, "");
  return `${base}/api/${path.replace(/^\//, "")}`;
}
