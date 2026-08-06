<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import ImageLightbox from "../components/post/ImageLightbox.vue";
import PostHero from "../components/post/PostHero.vue";
import PostSequenceNav from "../components/post/PostSequenceNav.vue";
import PostToc from "../components/post/PostToc.vue";
import RelatedPostsGrid from "../components/post/RelatedPostsGrid.vue";
import { setPageMeta } from "../composables/usePageMeta";
import { usePost } from "../composables/usePost";
import { useReadingProgress } from "../composables/useReadingProgress";
import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";
import { useTableOfContents } from "../composables/useTableOfContents";
import { useLightbox } from "../composables/useLightbox";
import { enhanceArticleBody } from "../lib/articleEnhancer";

const route = useRoute();
const { site, ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });

const articleBodyRef = ref(null);
const { readingProgress, update: updateReadingProgress } = useReadingProgress(articleBodyRef);
const { tableOfContents, activeHeading, buildNavigation, reset: resetNavigation, scrollToHeading } =
  useTableOfContents(articleBodyRef);
const { dialogRef, lightboxImage, open: openLightbox, close: closeLightbox, handleBackdropClick } =
  useLightbox();
let cleanupEnhancements = null;

const {
  post,
  error,
  loading,
  articleSections,
  hasFallbackSections,
  relatedPosts,
  previousPost,
  nextPost,
  loadPost,
} = usePost({ errorMessage: "这篇文章不存在，或仍是草稿未发布。" });

function updatePostMeta(currentPost = post.value) {
  if (!currentPost) return;
  const siteName = site.value?.name || "至知";
  setPageMeta({
    title: `${currentPost.title || "文章"} · ${siteName}`,
    description: currentPost.excerpt || `阅读《${currentPost.title || "文章"}》，记录技术实践、项目复盘与长期学习。`,
  });
}

function enhanceBody(body, headings) {
  cleanupEnhancements?.();
  cleanupEnhancements = enhanceArticleBody(body, headings, { openLightbox });
  updateReadingProgress();
}

async function buildArticleNavigation() {
  await buildNavigation(enhanceBody);
}

async function retryPost() {
  await loadPost(route.params.slug);
  await buildArticleNavigation();
  refreshReveal();
}

watch([post, loading, relatedPosts], () => {
  refreshReveal();
});

watch([post, site], () => {
  updatePostMeta();
});

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // Site meta is optional for the detail view.
  }

  await loadPost(route.params.slug);
  await buildArticleNavigation();
  refreshReveal();
});

watch(
  () => route.params.slug,
  async (slug) => {
    if (slug) {
      closeLightbox();
      readingProgress.value = 0;
      await loadPost(slug);
      await buildArticleNavigation();
      refreshReveal();
    }
  },
);

onBeforeUnmount(() => {
  closeLightbox();
  resetNavigation();
  cleanupEnhancements?.();
  cleanupEnhancements = null;
});
</script>

<template>
  <div class="post-view print-post-view">
    <div
      v-if="post"
      class="article-reading-progress"
      :style="{ transform: `scaleX(${readingProgress})` }"
      aria-hidden="true"
    ></div>
    <AsyncState
      v-if="loading"
      loading
      loading-message="文章页面正在展开……"
    />

    <section v-else-if="error" class="print-page print-section post-empty-state">
      <div class="sec-hd rv">
        <span class="sec-hd__n">404</span>
        <h1 class="sec-hd__t">文章没有找到</h1>
        <div class="sec-hd__line"></div>
      </div>
      <AsyncState
        :error="error"
        empty-message="请返回文章目录，或稍后重试。"
        @retry="retryPost"
      />
      <div class="print-cover__actions rv">
        <RouterLink to="/posts" class="cover-button primary-link">返回文章列表</RouterLink>
        <RouterLink to="/" class="cover-button">回到首页</RouterLink>
      </div>
    </section>

    <article v-else-if="post" class="print-page print-article-detail">
      <div class="post-topline print-post-topline rv">
        <RouterLink to="/posts">← 返回文章</RouterLink>
        <span>{{ site?.name || "Personal Blog" }} · Digital Edition</span>
      </div>

      <PostHero :post="post" :site-name="site?.name || 'Personal Blog'" />

      <div class="post-reading-layout" :class="{ 'post-reading-layout--no-toc': !tableOfContents.length }">
        <PostToc
          v-if="tableOfContents.length"
          :items="tableOfContents"
          :active-id="activeHeading"
          @navigate="scrollToHeading"
        />

        <section
          v-if="post.html_content"
          ref="articleBodyRef"
          class="post-body markdown-body print-markdown rv"
          data-reveal-delay="120"
          v-html="post.html_content"
        ></section>

        <section v-else-if="hasFallbackSections" class="post-body print-markdown rv">
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

        <p v-else class="feedback post-body rv">这篇文章暂时还没有正文内容。</p>
      </div>

      <PostSequenceNav
        v-if="previousPost || nextPost"
        :previous-post="previousPost"
        :next-post="nextPost"
      />      <span class="pg pg--r">— Article —</span>
    </article>

    <ImageLightbox
      ref="dialogRef"
      :src="lightboxImage.src"
      :alt="lightboxImage.alt"
      @close="closeLightbox"
      @backdrop="handleBackdropClick"
    />

    <RelatedPostsGrid v-if="relatedPosts.length" :posts="relatedPosts" />
  </div>
</template>
