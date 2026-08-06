import { computed, onScopeDispose, ref } from "vue";

import { getPost, isRequestAbort } from "../services/api";

const DEFAULT_POST_ERROR = "这篇文章不存在，或仍是草稿未发布。";

export function usePost({ errorMessage = DEFAULT_POST_ERROR } = {}) {
  const post = ref(null);
  const error = ref("");
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
      loading.value = false;
      return null;
    }

    loading.value = true;
    error.value = "";
    post.value = null;

    try {
      const data = await getPost(slug, { signal: activeController.signal });
      if (requestId !== requestSequence) return null;
      post.value = data;
      return data;
    } catch (err) {
      if (requestId === requestSequence && !isRequestAbort(err)) {
        error.value = err?.code === "REQUEST_TIMEOUT"
          ? "文章加载超时，请稍后重试。"
          : errorMessage;
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
    loading,
    relatedPosts,
    previousPost,
    nextPost,
    loadPost,
  };
}
