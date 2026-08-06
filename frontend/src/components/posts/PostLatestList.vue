<script setup>
import { RouterLink } from "vue-router";

import { displayDate } from "../../composables/useFormat";

defineProps({
  posts: { type: Array, required: true },
});
</script>

<template>
  <div class="article-list print-article-list unified-latest-list">
    <RouterLink
      v-for="(post, index) in posts"
      :key="post.slug"
      :to="`/posts/${post.slug}`"
      class="article-item print-list-item rv"
      :class="{ 'article-item--has-cover': !!post.cover_image }"
      :data-reveal-delay="Math.min(index, 8) * 45"
    >
      <img
        v-if="post.cover_image"
        class="article-item__thumb"
        :src="post.cover_image"
        alt=""
        width="132"
        height="99"
        loading="lazy"
        decoding="async"
        @error="(event) => event.target.classList.add('is-broken')"
      >
      <div class="article-meta">
        <span>{{ displayDate(post.published_at) }}</span>
        <span>{{ post.read_time }}</span>
      </div>
      <h2>{{ post.title }}</h2>
      <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
      <div class="post-card-tags list-tags">
        <span v-for="tag in post.tags" :key="tag" class="tag tag--code">{{ tag }}</span>
      </div>
    </RouterLink>
  </div>
</template>
