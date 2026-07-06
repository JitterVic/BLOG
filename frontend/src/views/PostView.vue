<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { useSite } from "../composables/useSite";
import { getPost } from "../services/api";

const route = useRoute();
const { site, ensureSite } = useSite();

const post = ref(null);
const error = ref("");
const loading = ref(false);

const articleSections = computed(() => post.value?.sections || []);
const hasFallbackSections = computed(() => !post.value?.html_content && articleSections.value.length > 0);
const relatedPosts = computed(() => post.value?.related_posts || []);

async function loadPost(slug) {
  loading.value = true;
  error.value = "";
  post.value = null;

  try {
    post.value = await getPost(slug);
  } catch (err) {
    error.value = "这篇文章不存在，或仍是草稿未发布。";
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // Site meta is optional for the detail view.
  }

  await loadPost(route.params.slug);
});

watch(
  () => route.params.slug,
  async (slug) => {
    if (slug) {
      await loadPost(slug);
    }
  },
);
</script>

<template>
  <div class="post-view">
    <p v-if="loading" class="feedback">文章页面正在展开……</p>

    <section v-else-if="error" class="paper-card post-shell post-empty-state">
      <p class="section-label">Not Found</p>
      <h1>文章没有找到</h1>
      <p>{{ error }}</p>
      <div class="home-hero-actions">
        <RouterLink to="/posts" class="cover-button primary-link">返回文章列表</RouterLink>
        <RouterLink to="/" class="cover-button">回到首页</RouterLink>
      </div>
    </section>

    <article v-else-if="post" class="paper-card post-shell">
      <div class="post-topline">
        <RouterLink to="/posts">← 返回文章</RouterLink>
        <span>{{ site?.name || "Personal Blog" }}</span>
      </div>

      <header class="post-hero">
        <p class="section-label">{{ post.category || "Article" }}</p>
        <h1>{{ post.title }}</h1>
        <p v-if="post.excerpt" class="post-subtitle">{{ post.excerpt }}</p>

        <div class="post-meta-row">
          <span>{{ post.published_at || "未设置日期" }}</span>
          <span>{{ post.read_time }}</span>
        </div>

        <blockquote v-if="post.hero_quote">{{ post.hero_quote }}</blockquote>

        <div v-if="post.tags?.length" class="post-card-tags detail-tags">
          <RouterLink v-for="tag in post.tags" :key="tag" :to="`/tags?tag=${encodeURIComponent(tag)}`">
            {{ tag }}
          </RouterLink>
        </div>
      </header>

      <section v-if="post.html_content" class="post-body markdown-body" v-html="post.html_content"></section>

      <section v-else-if="hasFallbackSections" class="post-body">
        <div
          v-for="section in articleSections"
          :key="section.heading"
          class="post-section"
        >
          <h2>{{ section.heading }}</h2>
          <p v-for="paragraph in section.paragraphs" :key="paragraph">
            {{ paragraph }}
          </p>
        </div>
      </section>

      <p v-else class="feedback post-body">这篇文章暂时还没有正文内容。</p>
    </article>

    <section v-if="relatedPosts.length" class="related-section">
      <div class="section-head">
        <div>
          <p class="section-label">Continue Reading</p>
          <h2>你也许还会想看</h2>
        </div>
      </div>

      <div class="related-grid">
        <RouterLink
          v-for="item in relatedPosts"
          :key="item.slug"
          :to="`/posts/${item.slug}`"
          class="paper-card related-card"
        >
          <span class="section-label">{{ item.category }}</span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.excerpt }}</p>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
