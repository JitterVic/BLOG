import { computed, ref } from "vue";

import { getPost } from "../services/api";

const DEFAULT_POST_ERROR = "这篇文章不存在，或仍是草稿未发布。";

export function usePost({ errorMessage = DEFAULT_POST_ERROR } = {}) {
  const post = ref(null);
  const error = ref("");
  const loading = ref(false);

  const articleSections = computed(() => post.value?.sections || []);
  const hasFallbackSections = computed(
    () => !post.value?.html_content && articleSections.value.length > 0,
  );
  const relatedPosts = computed(() => post.value?.related_posts || []);

  async function loadPost(slug) {
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
      const data = await getPost(slug);
      post.value = data;
      return data;
    } catch (err) {
      error.value = errorMessage;
      return null;
    } finally {
      loading.value = false;
    }
  }

  return {
    post,
    error,
    loading,
    articleSections,
    hasFallbackSections,
    relatedPosts,
    loadPost,
  };
}
