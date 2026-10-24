<script setup>
import { RouterLink } from "vue-router";

defineProps({
  previousPost: { type: Object, default: null },
  nextPost: { type: Object, default: null },
});
</script>

<template>
  <nav class="post-sequence-nav rv" aria-label="上一篇和下一篇">
    <RouterLink
      v-if="previousPost"
      :to="`/posts/${previousPost.slug}`"
      class="post-sequence-link post-sequence-link--previous"
      data-cursor="上一篇"
    >
      <span>← Previous</span>
      <strong>{{ previousPost.title }}</strong>
    </RouterLink>
    <span v-else class="post-sequence-placeholder"></span>
    <RouterLink
      v-if="nextPost"
      :to="`/posts/${nextPost.slug}`"
      class="post-sequence-link post-sequence-link--next"
      data-cursor="下一篇"
    >
      <span>Next →</span>
      <strong>{{ nextPost.title }}</strong>
    </RouterLink>
  </nav>
</template>
