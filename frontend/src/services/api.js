const API_ROOT = import.meta.env.VITE_API_ROOT || "/api";
const DEFAULT_TIMEOUT_MS = 10000;

export class ApiError extends Error {
  constructor(message, { status = 0, code = "API_ERROR", cause } = {}) {
    super(message, { cause });
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function isRequestAbort(error) {
  return error?.code === "REQUEST_ABORTED";
}

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

async function request(path, { signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  let timedOut = false;
  const abortFromCaller = () => controller.abort();
  if (signal?.aborted) controller.abort();
  signal?.addEventListener("abort", abortFromCaller, { once: true });
  const timeout = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(`${API_ROOT}${path}`, { signal: controller.signal });
    if (!response.ok) {
      throw new ApiError(`Request failed: ${response.status}`, {
        status: response.status,
        code: response.status === 404 ? "NOT_FOUND" : "HTTP_ERROR",
      });
    }

    try {
      return await response.json();
    } catch (error) {
      throw new ApiError("服务器返回了无法解析的数据。", {
        status: response.status,
        code: "INVALID_JSON",
        cause: error,
      });
    }
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new ApiError(timedOut ? "请求超时。" : "请求已取消。", {
        code: timedOut ? "REQUEST_TIMEOUT" : "REQUEST_ABORTED",
        cause: error,
      });
    }
    if (error instanceof ApiError) throw error;
    throw new ApiError("网络连接失败。", { code: "NETWORK_ERROR", cause: error });
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abortFromCaller);
  }
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
