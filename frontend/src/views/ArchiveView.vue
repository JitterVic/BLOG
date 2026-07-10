<script setup>
import { computed, onMounted } from "vue";
import { RouterLink } from "vue-router";

import { usePosts } from "../composables/usePosts";

const {
  posts,
  error,
  loading,
  loadPosts,
} = usePosts({ errorMessage: "归档加载失败，请稍后再试。" });

const groupedPosts = computed(() => {
  const groups = new Map();

  for (const post of posts.value) {
    const year = (post.published_at || "未归档").slice(0, 4);
    if (!groups.has(year)) {
      groups.set(year, []);
    }
    groups.get(year).push(post);
  }

  return Array.from(groups.entries());
});

function shortDate(value) {
  if (!value) return "--.--";
  const [, month, day] = value.split("-");
  return month && day ? `${month}-${day}` : value;
}

onMounted(async () => {
  await loadPosts();
});
</script>

<template>
  <div class="content-view print-subpage print-archive-page">
    <section class="print-page print-section">
      <div class="sec-hd rv vis">
        <span class="sec-hd__n">01</span>
        <h1 class="sec-hd__t">归档 Archive</h1>
        <div class="sec-hd__line"></div>
      </div>

      <div class="print-subpage__meta">
        <span>{{ posts.length }} 篇</span>
        <span>Chronological index</span>
      </div>

      <p v-if="error" class="feedback print-feedback">{{ error }}</p>
      <p v-else-if="loading" class="feedback print-feedback">归档正在整理中……</p>
      <p v-else-if="!posts.length" class="feedback print-feedback">暂无可归档的已发布文章。</p>

      <div v-else class="print-year-ledger">
        <section v-for="([year, items], index) in groupedPosts" :key="year" class="archive print-year-block">
          <div class="archive__year">
            <span>{{ year }}</span>
            <strong>{{ items.length }} 篇</strong>
          </div>
          <ul class="archive__list">
            <li v-for="post in items" :key="post.slug" class="archive__li">
              <span class="archive__date">{{ shortDate(post.published_at) }}</span>
              <RouterLink :to="`/posts/${post.slug}`" class="archive__title">{{ post.title }}</RouterLink>
              <span class="archive__tags">
                <span v-for="tag in post.tags?.slice(0, 2)" :key="tag" class="tag tag--code">{{ tag }}</span>
              </span>
            </li>
          </ul>
          <div v-if="index < groupedPosts.length - 1" class="orn">✦</div>
        </section>
      </div>

      <span class="pg pg--r">— Archive —</span>
    </section>
  </div>
</template>
