// HTTP 基础设施：统一的请求封装、超时、中止与错误归一化。

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

export async function request(path, { signal, timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
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
      throw new ApiError(`请求失败（HTTP ${response.status}）`, {
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
