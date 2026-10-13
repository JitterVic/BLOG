<script setup>
import { RouterLink } from "vue-router";

import { displayDate, formatClicks } from "../../composables/useFormat";

defineProps({
  posts: { type: Array, required: true },
});
</script>

<template>
  <div class="home-hot-ledger">
    <p class="home-hot-ledger__caption">Most Read · 按阅读量排序</p>
    <RouterLink
      v-for="(post, index) in posts"
      :key="post.slug"
      :to="`/posts/${post.slug}`"
      class="home-hot-row rv"
      :data-reveal-delay="index * 70"
    >
      <span class="home-hot-row__rank">{{ String(index + 1).padStart(2, "0") }}</span>
      <div class="home-hot-row__copy">
        <div class="home-hot-row__titleline">
          <h3>{{ post.title }}</h3>
          <!-- 点线 leader：把阅读量牵到行尾，避免视线横跨整行去寻找 -->
          <span class="home-hot-row__leader" aria-hidden="true"></span>
          <strong class="home-hot-row__clicks">{{ formatClicks(post.click_count) }}</strong>
        </div>
        <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
        <div class="home-hot-row__foot">
          <span class="home-hot-row__cat">{{ post.category || "Most Read" }}</span>
          <span>{{ displayDate(post.published_at) }}</span>
        </div>
      </div>
    </RouterLink>
  </div>
</template>
