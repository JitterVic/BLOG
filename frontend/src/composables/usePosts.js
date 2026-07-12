import { ref } from "vue";

import { getPosts } from "../services/api";

const DEFAULT_POSTS_ERROR = "文章列表加载失败，请稍后再试。";

export function usePosts({ errorMessage = DEFAULT_POSTS_ERROR } = {}) {
  const posts = ref([]);
  const error = ref("");
  const loading = ref(false);
  let requestSequence = 0;

  async function loadPosts(tagOrOptions = "", options = {}) {
    const requestId = ++requestSequence;
    loading.value = true;
    error.value = "";

    try {
      const list = await getPosts(tagOrOptions, options);
      if (requestId !== requestSequence) return [];
      posts.value = list;
      return list;
    } catch (err) {
      if (requestId === requestSequence) {
        posts.value = [];
        error.value = errorMessage;
      }
      return [];
    } finally {
      if (requestId === requestSequence) {
        loading.value = false;
      }
    }
  }

  return {
    posts,
    error,
    loading,
    loadPosts,
  };
}
