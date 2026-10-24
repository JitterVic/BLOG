<script setup>
// 文章页（DESIGN.md §5.3）：阅读第一——正文 18px / 行高 2 / 每行约 36 字。
// 版面：1100–1359px 正文在主栏内居中；≥1360px 预留边注列（第二阶段）。
// 左栏目录数据经 useRailState 共享；「读完」判定在文末哨兵处触发（§6.3）。

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import ImageLightbox from "../components/post/ImageLightbox.vue";
import PostRow from "../components/PostRow.vue";
import ReadingTools from "../components/post/ReadingTools.vue";
import { formatClicks, readTimeLabel } from "../composables/useFormat";
import { useLightbox } from "../composables/useLightbox";
import { setPageMeta } from "../composables/usePageMeta";
import { usePost } from "../composables/usePost";
import { useRailState } from "../composables/useRailState";
import { useReadLog } from "../composables/useReadLog";
import { useReadingProgress } from "../composables/useReadingProgress";
import { useSite } from "../composables/useSite";
import { useTableOfContents } from "../composables/useTableOfContents";
import { enhanceArticleBody } from "../lib/articleEnhancer";

const route = useRoute();
const { site, ensureSite } = useSite();
const { setArticle, setActiveHeading, setProgress, resetRailState } = useRailState();
const { isRead, markRead } = useReadLog();

const articleBodyRef = ref(null);
const readSentinelRef = ref(null);
const { readingProgress, update: updateReadingProgress } = useReadingProgress(articleBodyRef);
const { tableOfContents, activeHeading, buildNavigation, reset: resetNavigation, scrollToHeading } =
  useTableOfContents(articleBodyRef);
const { dialogRef, lightboxImage, open: openLightbox, close: closeLightbox, handleBackdropClick } =
  useLightbox();
let cleanupEnhancements = null;
let cleanupReadSentinel = null;

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

// 只有服务端真的说「没有这篇文章」才报 404；超时/断网/5xx 一律按加载失败呈现
const isNotFound = computed(() => errorCode.value === "NOT_FOUND");
const notFoundHint = "这个地址下没有内容。链接可能写错了，或文章已被移走。";
const loadFailedHint = "正文没能加载出来。检查网络后重试。";

const timeText = computed(() => readTimeLabel(post.value?.read_time));
const clicksText = computed(() => formatClicks(post.value?.click_count));

function updatePostMeta(currentPost = post.value) {
  if (!currentPost) return;
  const siteName = site.value?.name || "至知";
  setPageMeta({
    title: `${currentPost.title || "文章"} · ${siteName}`,
    description: currentPost.excerpt || `阅读《${currentPost.title || "文章"}》。`,
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

/** 左栏共享：文章目录 + 所属栏目（§4.2）。 */
function syncRail(currentPost = post.value) {
  setArticle({
    toc: tableOfContents.value,
    category: currentPost?.category || "",
  });
}

/**
 * 读完判定（§6.3）：正文末尾哨兵进入视口，且停留 ≥ min(15s, 预计时长 × 20%)。
 * 目的是防止一把拉到底刷读迹；已读文章不再观察。
 */
function setupReadSentinel(slug, readTimeText) {
  const element = readSentinelRef.value;
  if (!element || !slug || isRead(slug)) return;

  const match = String(readTimeText || "").match(/(\d+)\s*min/i);
  const minutes = match ? Number(match[1]) : 5;
  const dwellMs = Math.min(15000, Math.max(1000, minutes * 60 * 1000 * 0.2));

  let dwellTimer = 0;
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          if (!dwellTimer) {
            dwellTimer = window.setTimeout(() => {
              observer.disconnect();
              markRead(slug); // 落笔；读迹栏可见时播放描红动画（§6.3）
            }, dwellMs);
          }
        } else if (dwellTimer) {
          window.clearTimeout(dwellTimer);
          dwellTimer = 0;
        }
      }
    },
    { threshold: 0 },
  );
  observer.observe(element);

  return () => {
    observer.disconnect();
    if (dwellTimer) window.clearTimeout(dwellTimer);
  };
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

function teardownArticle() {
  closeLightbox();
  resetNavigation();
  cleanupEnhancements?.();
  cleanupEnhancements = null;
  cleanupReadSentinel?.();
  cleanupReadSentinel = null;
  resetRailState();
}

async function presentArticle(slug, savedPosition = null) {
  await loadPost(slug);
  if (!post.value) return;
  updatePostMeta();
  await buildArticleNavigation();
  syncRail();
  cleanupReadSentinel?.();
  cleanupReadSentinel = setupReadSentinel(post.value.slug, post.value.read_time);
  await restoreSavedScrollPosition(savedPosition);
}

async function retryPost() {
  await presentArticle(route.params.slug);
}

// 阅读进度 → 左栏百分比与窄屏顶栏进度线
watch(readingProgress, (value) => setProgress(value));
watch(activeHeading, (id) => setActiveHeading(id));
watch(tableOfContents, () => syncRail());
watch([post, site], () => updatePostMeta());

onMounted(async () => {
  const savedScrollPosition = getSavedScrollPosition();
  try {
    await ensureSite();
  } catch (err) {
    // 站点元信息缺失不阻塞正文
  }
  await presentArticle(route.params.slug, savedScrollPosition);
});

watch(
  () => route.params.slug,
  async (slug) => {
    if (!slug) return;
    const savedScrollPosition = getSavedScrollPosition();
    teardownArticle();
    readingProgress.value = 0;
    await presentArticle(slug, savedScrollPosition);
  },
);

onBeforeUnmount(teardownArticle);
</script>

<template>
  <div class="post-view">
    <AsyncState
      v-if="loading"
      loading
      variant="post"
      loading-message="正在加载…"
    />

    <section v-else-if="error" class="state" :role="isNotFound ? 'status' : 'alert'">
      <h1 class="state__title">{{ isNotFound ? "找不到这一篇" : "文章没能加载出来" }}</h1>
      <p class="state__text">{{ isNotFound ? notFoundHint : loadFailedHint }}</p>
      <div class="state__actions state__actions--row">
        <button v-if="!isNotFound" type="button" class="btn" @click="retryPost">重试</button>
        <RouterLink class="text-link" to="/posts">全部文章</RouterLink>
        <RouterLink class="text-link" to="/">回首页</RouterLink>
      </div>
    </section>

    <article v-else-if="post" class="article">
      <!-- 文章头（§5.3）-->
      <header class="article-head">
        <p v-if="post.category" class="article-head__category">
          <RouterLink class="text-link" :to="{ name: 'posts', query: { cat: post.category } }">
            {{ post.category }}
          </RouterLink>
        </p>
        <h1 class="article-head__title">{{ post.title }}</h1>
        <p v-if="post.excerpt" class="article-head__excerpt">{{ post.excerpt }}</p>
        <div class="article-head__meta">
          <p class="article-head__meta-info">
            <time :datetime="post.published_at">{{ post.published_at }}</time>
            <span>{{ timeText }}</span>
            <span>{{ clicksText }}</span>
          </p>
          <ReadingTools />
        </div>

        <!-- 窄屏目录（§4.3）：左栏不在场时由 <details> 承担，不做动画 -->
        <details v-if="tableOfContents.length" class="article-toc-compact">
          <summary>目录</summary>
          <nav aria-label="本文目录">
            <a
              v-for="item in tableOfContents"
              :key="item.id"
              :href="`#${item.id}`"
              :class="{ 'article-toc-compact__sub': item.level === 3 }"
              @click.prevent="scrollToHeading(item.id)"
            >{{ item.label }}</a>
          </nav>
        </details>

        <figure v-if="post.cover_image" class="article-head__cover">
          <img :src="post.cover_image" :alt="post.title" decoding="async">
          <figcaption v-if="post.excerpt">{{ post.excerpt }}</figcaption>
        </figure>
      </header>

      <!-- 正文 -->
      <section
        v-if="post.html_content"
        ref="articleBodyRef"
        class="article-body prose"
        v-html="post.html_content"
      ></section>
      <section v-else-if="hasFallbackSections" ref="articleBodyRef" class="article-body prose">
        <div v-for="section in articleSections" :key="section.heading">
          <h2>{{ section.heading }}</h2>
          <p v-for="paragraph in section.paragraphs" :key="paragraph">{{ paragraph }}</p>
        </div>
      </section>
      <p v-else class="article-body prose">这篇文章暂时还没有正文内容。</p>

      <!-- 读完哨兵（§6.3）：不占版面，只负责判定 -->
      <div ref="readSentinelRef" class="read-sentinel" aria-hidden="true"></div>

      <!-- 文末（§5.3）-->
      <footer class="article-foot">
        <p v-if="post.tags?.length" class="article-foot__tags">
          <span>标签：</span>
          <template v-for="(tag, index) in post.tags" :key="tag">
            <RouterLink class="text-link" :to="{ name: 'posts', query: { q: tag } }">{{ tag }}</RouterLink>
            <span v-if="index < post.tags.length - 1" aria-hidden="true">　</span>
          </template>
        </p>

        <nav v-if="previousPost || nextPost" class="article-foot__adjacent" aria-label="相邻文章">
          <RouterLink v-if="previousPost" class="adjacent-link" :to="{ name: 'post', params: { slug: previousPost.slug } }">
            <span class="adjacent-link__dir">上一篇</span>
            <span class="adjacent-link__title">{{ previousPost.title }}</span>
          </RouterLink>
          <span v-else class="adjacent-link adjacent-link--empty"></span>
          <RouterLink v-if="nextPost" class="adjacent-link adjacent-link--next" :to="{ name: 'post', params: { slug: nextPost.slug } }">
            <span class="adjacent-link__dir">下一篇</span>
            <span class="adjacent-link__title">{{ nextPost.title }}</span>
          </RouterLink>
        </nav>

        <section v-if="relatedPosts.length" class="article-foot__related" aria-label="相关推荐">
          <h2>相关推荐</h2>
          <PostRow v-for="item in relatedPosts" :key="item.slug" :post="item" date-format="short" />
        </section>
      </footer>
    </article>

    <ImageLightbox
      ref="dialogRef"
      :src="lightboxImage.src"
      :alt="lightboxImage.alt"
      @close="closeLightbox"
      @backdrop="handleBackdropClick"
    />
  </div>
</template>
