<script setup>
// 「读得最多」榜单（DESIGN.md §5.1）：5 篇，名次是真实的顺序。
// 数字直接显示，不做 count-up；榜首无特殊装饰。整行可点，标题是唯一 tab 停靠点。

import { RouterLink } from "vue-router";

import { formatClicks } from "../../composables/useFormat";
import { useTitleMorph } from "../../composables/useTitleMorph";

defineProps({
  posts: { type: Array, default: () => [] },
});

const { handleOpen } = useTitleMorph();
</script>

<template>
  <ol v-if="posts.length" class="top-list">
    <li v-for="(post, index) in posts" :key="post.slug" class="top-row">
      <span class="top-row__rank" aria-hidden="true">{{ index + 1 }}</span>
      <RouterLink
        class="top-row__title"
        :to="{ name: 'post', params: { slug: post.slug } }"
        @click="handleOpen($event, { name: 'post', params: { slug: post.slug } })"
      >{{ post.title }}</RouterLink>
      <span class="top-row__clicks">{{ formatClicks(post.click_count) }}</span>
    </li>
  </ol>
  <p v-else class="top-list__empty">还没有阅读数据。</p>
</template>
