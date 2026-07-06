<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { getPosts } from "../services/api";

const posts = ref([]);
const error = ref("");
const loading = ref(false);

onMounted(async () => {
  loading.value = true;
  error.value = "";

  try {
    posts.value = await getPosts();
  } catch (err) {
    error.value = "文章列表加载失败，请稍后再试。";
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
          <p class="section-label">Writing</p>
          <h2>文章</h2>
        </div>
        <span class="muted-count">{{ posts.length }} 篇已发布</span>
      </div>

      <p v-if="error" class="feedback">{{ error }}</p>
      <p v-else-if="loading" class="feedback">文章正在加载中……</p>
      <p v-else-if="!posts.length" class="feedback">还没有已发布文章，先去后台发布第一篇。</p>

      <div v-else class="article-list">
        <RouterLink
          v-for="post in posts"
          :key="post.slug"
          :to="`/posts/${post.slug}`"
          class="article-item"
        >
          <div class="article-meta">
            <span>{{ post.published_at || "未设置日期" }}</span>
            <span>{{ post.read_time }}</span>
          </div>
          <h3>{{ post.title }}</h3>
          <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
          <div class="post-card-tags list-tags">
            <span v-for="tag in post.tags" :key="tag">{{ tag }}</span>
          </div>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
