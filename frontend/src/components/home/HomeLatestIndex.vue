<script setup>
import { RouterLink } from "vue-router";

import { displayDate } from "../../composables/useFormat";

defineProps({
  posts: { type: Array, required: true },
});
</script>

<template>
  <div class="home-latest-index">
    <p class="home-latest-index__caption">本期其余 · In This Issue</p>
    <RouterLink
      v-for="(post, index) in posts"
      :key="post.slug"
      :to="`/posts/${post.slug}`"
      class="home-index-row rv"
      :data-reveal-delay="index * 60"
    >
      <span class="home-index-row__number">{{ String(index + 2).padStart(2, "0") }}</span>
      <span class="home-index-row__date">{{ displayDate(post.published_at) }}</span>
      <div class="home-index-row__body">
        <strong>{{ post.title }}</strong>
        <p class="home-index-row__excerpt">{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
      </div>
      <small>{{ post.category || "Article" }} · {{ post.read_time }}</small>
    </RouterLink>
  </div>
</template>
