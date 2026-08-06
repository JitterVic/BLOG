<script setup>
import { RouterLink } from "vue-router";

import { displayDate, formatClicks } from "../../composables/useFormat";

defineProps({
  posts: { type: Array, required: true },
});
</script>

<template>
  <div class="home-hot-ledger">
    <RouterLink
      v-for="(post, index) in posts"
      :key="post.slug"
      :to="`/posts/${post.slug}`"
      class="home-hot-row rv"
      :data-reveal-delay="index * 70"
    >
      <span class="home-hot-row__rank">{{ String(index + 1).padStart(2, "0") }}</span>
      <div class="home-hot-row__copy">
        <span class="art__cat">{{ post.category || "Most Read" }}</span>
        <h3>{{ post.title }}</h3>
        <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
      </div>
      <div class="home-hot-row__meta">
        <strong>{{ formatClicks(post.click_count) }}</strong>
        <span>{{ displayDate(post.published_at) }}</span>
      </div>
    </RouterLink>
  </div>
</template>
