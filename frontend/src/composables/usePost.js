import { computed, onScopeDispose, ref } from "vue";

import { getPost, isRequestAbort } from "../services/api";

const DEFAULT_POST_ERROR = "这篇文章不存在，或仍是草稿未发布。";

/**
 * 错误码 → 文案。
 * 以前无论超时、断网还是 5xx，一律落到「文章不存在」，读者会以为文章被删了；
 * 现在只有真的 404 才这么说，其余情况如实说明是加载出了问题。
 */
function messageForError(err, fallback) {
  switch (err?.code) {
    case "REQUEST_TIMEOUT":
      return "文章加载超时，请稍后重试。";
    case "NETWORK_ERROR":
      return "网络连接失败，请检查网络后重试。";
    case "INVALID_JSON":
      return "服务器返回了异常内容，请稍后重试。";
    case "HTTP_ERROR":
      return "文章暂时无法加载，请稍后重试。";
    case "NOT_FOUND":
      return fallback;
    default:
      return fallback;
  }
}

export function usePost({ errorMessage = DEFAULT_POST_ERROR } = {}) {
  const post = ref(null);
  const error = ref("");
  /** 最近一次失败的归一化错误码，供视图区分「文章不存在」与「加载失败」。 */
  const errorCode = ref("");
  const loading = ref(false);
  let requestSequence = 0;
  let activeController = null;

  const relatedPosts = computed(() => post.value?.related_posts || []);
  const previousPost = computed(() => post.value?.previous_post || null);
  const nextPost = computed(() => post.value?.next_post || null);

  async function loadPost(slug) {
    const requestId = ++requestSequence;
    activeController?.abort();
    activeController = new AbortController();

    if (!slug) {
      post.value = null;
      error.value = errorMessage;
      errorCode.value = "NOT_FOUND";
      loading.value = false;
      return null;
    }

    loading.value = true;
    error.value = "";
    errorCode.value = "";
    post.value = null;

    try {
      const data = await getPost(slug, { signal: activeController.signal });
      if (requestId !== requestSequence) return null;
      post.value = data;
      return data;
    } catch (err) {
      if (requestId === requestSequence && !isRequestAbort(err)) {
        error.value = messageForError(err, errorMessage);
        errorCode.value = err?.code || "API_ERROR";
      }
      return null;
    } finally {
      if (requestId === requestSequence) loading.value = false;
    }
  }

  onScopeDispose(() => activeController?.abort());

  return {
    post,
    error,
    errorCode,
    loading,
    relatedPosts,
    previousPost,
    nextPost,
    loadPost,
  };
}
