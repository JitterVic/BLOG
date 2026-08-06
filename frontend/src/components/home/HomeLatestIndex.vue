<script setup>
import { RouterLink } from "vue-router";

import { displayDate } from "../../composables/useFormat";

defineProps({
  posts: { type: Array, required: true },
});
</script>

<template>
  <div class="home-latest-index">
    <RouterLink
      v-for="(post, index) in posts"
      :key="post.slug"
      :to="`/posts/${post.slug}`"
      class="home-index-row rv"
      :data-reveal-delay="index * 60"
    >
      <span class="home-index-row__number">{{ String(index + 2).padStart(2, "0") }}</span>
      <span class="home-index-row__date">{{ displayDate(post.published_at) }}</span>
      <strong>{{ post.title }}</strong>
      <small>{{ post.category || "Article" }} · {{ post.read_time }}</small>
    </RouterLink>
  </div>
</template>
