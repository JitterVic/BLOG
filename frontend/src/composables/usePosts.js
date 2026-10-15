import { onScopeDispose, ref } from "vue";

import { getPosts, isRequestAbort } from "../services/api";

const DEFAULT_POSTS_ERROR = "文章列表加载失败，请稍后再试。";

export function usePosts({ errorMessage = DEFAULT_POSTS_ERROR } = {}) {
  const posts = ref([]);
  const error = ref("");
  const loading = ref(false);
  const loadingMore = ref(false);
  const loadMoreError = ref("");
  const total = ref(0);
  const page = ref(1);
  const hasMore = ref(false);
  let requestSequence = 0;
  let activeController = null;
  let lastParams = null;

  // /api/posts 只有一种形状（永远带信封），所以这里不再分裸数组那条支路。
  function applyListResult(list, { append = false } = {}) {
    const items = Array.isArray(list?.items) ? list.items : [];
    posts.value = append ? posts.value.concat(items) : items;
    total.value = Number.isFinite(list?.total) ? list.total : posts.value.length;
    page.value = Number.isFinite(list?.page) ? list.page : 1;
    hasMore.value = Boolean(list?.has_more);
  }

  async function loadPosts(tagOrOptions = "", options = {}) {
    const requestId = ++requestSequence;
    activeController?.abort();
    activeController = new AbortController();
    loading.value = true;
    error.value = "";
    loadMoreError.value = "";

    const normalized = typeof tagOrOptions === "object"
      ? { ...tagOrOptions }
      : { ...options, tag: tagOrOptions };
    const { signal: _callerSignal, timeoutMs, ...params } = normalized;

    try {
      const list = await getPosts({ ...normalized, signal: activeController.signal });
      if (requestId !== requestSequence) return [];
      lastParams = params;
      applyListResult(list);
      return posts.value;
    } catch (err) {
      if (requestId === requestSequence && !isRequestAbort(err)) {
        posts.value = [];
        total.value = 0;
        page.value = 1;
        hasMore.value = false;
        error.value = err?.code === "REQUEST_TIMEOUT"
          ? "文章列表加载超时，请稍后重试。"
          : errorMessage;
      }
      return [];
    } finally {
      if (requestId === requestSequence) loading.value = false;
    }
  }

  async function loadMore() {
    if (!hasMore.value || loading.value || loadingMore.value || !lastParams) return [];

    const requestId = ++requestSequence;
    activeController?.abort();
    activeController = new AbortController();
    loadingMore.value = true;
    loadMoreError.value = "";

    try {
      const list = await getPosts({
        ...lastParams,
        page: page.value + 1,
        signal: activeController.signal,
      });
      if (requestId !== requestSequence) return [];
      applyListResult(list, { append: true });
      return posts.value;
    } catch (err) {
      if (requestId === requestSequence && !isRequestAbort(err)) {
        loadMoreError.value = err?.code === "REQUEST_TIMEOUT"
          ? "加载更多超时，请重试。"
          : "加载更多失败，请重试。";
      }
      return [];
    } finally {
      if (requestId === requestSequence) loadingMore.value = false;
    }
  }

  onScopeDispose(() => activeController?.abort());

  return {
    posts,
    error,
    loading,
    loadingMore,
    loadMoreError,
    total,
    page,
    hasMore,
    loadPosts,
    loadMore,
  };
}
