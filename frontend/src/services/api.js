// API 端点层：只负责拼接接口路径，底层请求能力来自 http.js。

import { request } from "./http";

// 保持既有导入路径兼容（旧代码从 services/api 引入错误类型）。
export { ApiError, isRequestAbort } from "./http";

function buildQueryString(params = {}) {
  const search = new URLSearchParams();
  if (params.tag) search.set("tag", params.tag);
  if (params.q) search.set("q", params.q);
  if (params.sort) search.set("sort", params.sort);
  if (params.limit) search.set("limit", String(params.limit));
  if (params.page) search.set("page", String(params.page));
  const query = search.toString();
  return query ? `?${query}` : "";
}

function normalizePostListParams(tagOrOptions = "", options = {}) {
  if (typeof tagOrOptions === "object") return tagOrOptions;
  return { ...options, tag: tagOrOptions };
}

export function getSite(options = {}) {
  return request("/site", options);
}

export function getPosts(tagOrOptions = "", options = {}) {
  const params = normalizePostListParams(tagOrOptions, options);
  const { signal, timeoutMs, ...queryParams } = params;
  return request(`/posts${buildQueryString(queryParams)}`, { signal, timeoutMs });
}

export function getPost(slug, options = {}) {
  return request(`/posts/${encodeURIComponent(slug)}`, options);
}
