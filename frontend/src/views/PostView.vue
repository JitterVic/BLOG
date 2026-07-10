<script setup>
import { onMounted, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { usePost } from "../composables/usePost";
import { useSite } from "../composables/useSite";

const route = useRoute();
const { site, ensureSite } = useSite();

const {
  post,
  error,
  loading,
  articleSections,
  hasFallbackSections,
  relatedPosts,
  loadPost,
} = usePost({ errorMessage: "这篇文章不存在，或仍是草稿未发布。" });

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
  <div class="post-view print-post-view">
    <p v-if="loading" class="feedback print-feedback">文章页面正在展开……</p>

    <section v-else-if="error" class="print-page print-section post-empty-state">
      <div class="sec-hd rv vis">
        <span class="sec-hd__n">404</span>
        <h1 class="sec-hd__t">文章没有找到</h1>
        <div class="sec-hd__line"></div>
      </div>
      <p class="feedback print-feedback">{{ error }}</p>
      <div class="print-cover__actions">
        <RouterLink to="/posts" class="cover-button primary-link">返回文章列表</RouterLink>
        <RouterLink to="/" class="cover-button">回到首页</RouterLink>
      </div>
    </section>

    <article v-else-if="post" class="print-page print-article-detail">
      <div class="post-topline print-post-topline">
        <RouterLink to="/posts">← 返回文章</RouterLink>
        <span>{{ site?.name || "Personal Blog" }} · Digital Edition</span>
      </div>

      <header class="post-hero print-post-hero">
        <p class="section-label">{{ post.category || "Article" }}</p>
        <h1>{{ post.title }}</h1>
        <p v-if="post.excerpt" class="post-subtitle">{{ post.excerpt }}</p>

        <div class="post-meta-row">
          <span>{{ post.published_at || "未设置日期" }}</span>
          <span>{{ post.read_time }}</span>
        </div>

        <blockquote v-if="post.hero_quote">{{ post.hero_quote }}</blockquote>

        <div v-if="post.tags?.length" class="post-card-tags detail-tags print-detail-tags">
          <RouterLink v-for="tag in post.tags" :key="tag" :to="`/tags?tag=${encodeURIComponent(tag)}`" class="tag tag--code">
            {{ tag }}
          </RouterLink>
        </div>
      </header>

      <section v-if="post.html_content" class="post-body markdown-body print-markdown" v-html="post.html_content"></section>

      <section v-else-if="hasFallbackSections" class="post-body print-markdown">
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
      <span class="pg pg--r">— Article —</span>
    </article>

    <section v-if="relatedPosts.length" class="related-section print-related-section">
      <div class="sec-hd rv vis">
        <span class="sec-hd__n">Next</span>
        <h2 class="sec-hd__t">你也许还会想看</h2>
        <div class="sec-hd__line"></div>
      </div>

      <div class="g2e print-related-grid">
        <RouterLink
          v-for="item in relatedPosts"
          :key="item.slug"
          :to="`/posts/${item.slug}`"
          class="art print-article-strip"
        >
          <span class="section-label">{{ item.category }}</span>
          <h3 class="art__t">{{ item.title }}</h3>
          <p class="art__p">{{ item.excerpt }}</p>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
