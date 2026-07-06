<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { getPosts } from "../services/api";

const posts = ref([]);
const error = ref("");
const loading = ref(false);

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

onMounted(async () => {
  loading.value = true;
  error.value = "";

  try {
    posts.value = await getPosts();
  } catch (err) {
    error.value = "归档加载失败，请稍后再试。";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="content-view">
    <section class="simple-section">
      <div class="section-head">
        <div>
          <p class="section-label">Archive</p>
          <h2>归档</h2>
        </div>
        <span class="muted-count">{{ posts.length }} 篇</span>
      </div>

      <p v-if="error" class="feedback">{{ error }}</p>
      <p v-else-if="loading" class="feedback">归档正在整理中……</p>
      <p v-else-if="!posts.length" class="feedback">暂无可归档的已发布文章。</p>

      <div v-else class="year-groups">
        <section
          v-for="[year, items] in groupedPosts"
          :key="year"
          class="simple-card year-card"
        >
          <div class="year-head">
            <strong>{{ year }}</strong>
            <span>{{ items.length }} 篇</span>
          </div>

          <div class="year-posts">
            <RouterLink
              v-for="post in items"
              :key="post.slug"
              :to="`/posts/${post.slug}`"
              class="year-post-link"
            >
              <span>{{ post.published_at || "未设置日期" }}</span>
              <p>{{ post.title }}</p>
            </RouterLink>
          </div>
        </section>
      </div>
    </section>
  </div>
</template>
