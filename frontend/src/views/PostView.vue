<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import ImageLightbox from "../components/post/ImageLightbox.vue";
import PostHero from "../components/post/PostHero.vue";
import PostRail from "../components/post/PostRail.vue";
import PostSequenceNav from "../components/post/PostSequenceNav.vue";
import PostToc from "../components/post/PostToc.vue";
import RelatedPostsGrid from "../components/post/RelatedPostsGrid.vue";
import { useMediaQuery } from "../composables/useMediaQuery";
import { setPageMeta } from "../composables/usePageMeta";
import { usePost } from "../composables/usePost";
import { usePostRail } from "../composables/usePostRail";
import { useReadingProgress } from "../composables/useReadingProgress";
import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";
import { useTableOfContents } from "../composables/useTableOfContents";
import { useLightbox } from "../composables/useLightbox";
import { enhanceArticleBody } from "../lib/articleEnhancer";

const route = useRoute();
const { site, ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });

// 左侧清单只在阅读版式真有那条空轨道时才存在。断点同时管住渲染与请求：
// 窄屏既不该多拿一份列表，也不该把它塞进单列版式里。断点值必须与 post.css 的
// `@media (min-width: 1440px)` 一致，否则会出现「渲染了、发了请求，却被 CSS 藏起来」。
const railEnabled = useMediaQuery("(min-width: 1440px)");
const {
  railPosts,
  railTotal,
  railHasMore,
  railLoadingMore,
  railMode,
  railCategory,
  ensureRail,
  setRailScope,
  loadMoreRail,
} = usePostRail();
const showRail = computed(() => railEnabled.value && railPosts.value.length > 0);

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
  errorCode,
  loading,
  articleSections,
  hasFallbackSections,
  relatedPosts,
  previousPost,
  nextPost,
  loadPost,
} = usePost({ errorMessage: "这篇文章不存在，或仍是草稿未发布。" });

// 只有服务端真的说「没有这篇文章」才报 404；超时/断网/5xx 一律按加载失败呈现，
// 否则一次网络抖动就会告诉读者「文章不存在」，是很伤信任的误报。
const isNotFound = computed(() => errorCode.value === "NOT_FOUND");
const errorIssueNumber = computed(() => (isNotFound.value ? "404" : "ERR"));
const errorHeadline = computed(() => (isNotFound.value ? "文章没有找到" : "文章加载受阻"));
const errorHint = computed(() => (
  isNotFound.value
    ? "这篇文章可能已被移动或撤下，可以回到目录继续浏览。"
    : "正文没有取回来，通常是网络或服务端临时故障，可以稍后重试。"
));

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

/**
 * 拉取左侧清单。不 await：清单是旁路内容，不能拖住正文渲染与滚动位置恢复。
 * 数据到了之后再补一次入场观察 —— 清单是在 refreshReveal 之后才挂上去的，
 * 观察器没见过它就永远不会给它加 .vis，整栏会一直停在不透明 0 的初始态。
 */
function syncRail() {
  if (!railEnabled.value) return;
  void ensureRail(post.value?.category || "");
}

function getSavedScrollPosition() {
  const savedPosition = window.history.state?.scroll;
  const top = Number(savedPosition?.top);
  const left = Number(savedPosition?.left);
  if (!Number.isFinite(top) || !Number.isFinite(left)) return null;
  return { top, left };
}

async function restoreSavedScrollPosition(savedPosition) {
  if (!savedPosition) return;
  await nextTick();
  await new Promise((resolve) => {
    window.requestAnimationFrame(() => window.requestAnimationFrame(resolve));
  });
  window.scrollTo({ ...savedPosition, behavior: "auto" });
  updateReadingProgress();
}

async function retryPost() {
  await loadPost(route.params.slug);
  await buildArticleNavigation();
  syncRail();
  refreshReveal();
}

watch([post, loading, relatedPosts], () => {
  refreshReveal();
});

watch([post, site], () => {
  updatePostMeta();
});

watch(railEnabled, (enabled) => {
  if (enabled) syncRail();
});

onMounted(async () => {
  const savedScrollPosition = getSavedScrollPosition();
  try {
    await ensureSite();
  } catch (err) {
    // Site meta is optional for the detail view.
  }

  await loadPost(route.params.slug);
  await buildArticleNavigation();
  syncRail();
  await restoreSavedScrollPosition(savedScrollPosition);
  refreshReveal();
});

watch(
  () => route.params.slug,
  async (slug) => {
    if (slug) {
      const savedScrollPosition = getSavedScrollPosition();
      closeLightbox();
      readingProgress.value = 0;
      await loadPost(slug);
      await buildArticleNavigation();
      syncRail();
      await restoreSavedScrollPosition(savedScrollPosition);
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
      variant="post"
      loading-message="文章正在排版装订……"
    />

    <section v-else-if="error" class="print-page print-section post-empty-state">
      <div class="sec-hd rv">
        <span class="sec-hd__n">{{ errorIssueNumber }}</span>
        <h1 class="sec-hd__t">{{ errorHeadline }}</h1>
        <div class="sec-hd__line"></div>
      </div>
      <AsyncState
        :error="error"
        :empty-message="isNotFound ? '请返回文章目录，或稍后重试。' : errorHint"
        :retry-label="isNotFound ? '重新装订' : '重试加载'"
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

      <div
        class="post-reading-layout"
        :class="{
          'post-reading-layout--no-toc': !tableOfContents.length,
          'post-reading-layout--no-rail': !showRail,
        }"
      >
        <PostRail
          v-if="showRail"
          :posts="railPosts"
          :total="railTotal"
          :has-more="railHasMore"
          :loading-more="railLoadingMore"
          :mode="railMode"
          :category="railCategory"
          :follow-category="post.category || ''"
          :categories="site?.categories || []"
          :current-slug="route.params.slug"
          @more="loadMoreRail"
          @select-scope="setRailScope"
        />

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
