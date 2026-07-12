<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { usePost } from "../composables/usePost";
import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";

const route = useRoute();
const { site, ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });
const articleBodyRef = ref(null);
const tableOfContents = ref([]);
const activeHeading = ref("");
let headingObserver = null;

const {
  post,
  error,
  loading,
  articleSections,
  hasFallbackSections,
  relatedPosts,
  loadPost,
} = usePost({ errorMessage: "这篇文章不存在，或仍是草稿未发布。" });

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function disconnectHeadingObserver() {
  headingObserver?.disconnect();
  headingObserver = null;
}

async function buildArticleNavigation() {
  disconnectHeadingObserver();
  tableOfContents.value = [];
  activeHeading.value = "";
  await nextTick();

  const body = articleBodyRef.value;
  if (!body) return;

  const headings = Array.from(body.querySelectorAll("h2, h3"));
  tableOfContents.value = headings.map((heading, index) => {
    if (!heading.id) heading.id = `article-section-${index + 1}`;
    return {
      id: heading.id,
      label: heading.textContent?.trim() || `章节 ${index + 1}`,
      level: heading.tagName === "H3" ? 3 : 2,
    };
  });

  if (!tableOfContents.value.length) return;
  activeHeading.value = tableOfContents.value[0].id;

  if (!("IntersectionObserver" in window)) return;
  headingObserver = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible[0]) activeHeading.value = visible[0].target.id;
    },
    { rootMargin: "-18% 0px -68% 0px", threshold: [0, 1] },
  );
  headings.forEach((heading) => headingObserver.observe(heading));
}

function scrollToHeading(id) {
  const heading = document.getElementById(id);
  if (!heading) return;
  heading.scrollIntoView({
    behavior: prefersReducedMotion() ? "auto" : "smooth",
    block: "start",
  });
  activeHeading.value = id;
}

watch([post, loading, relatedPosts], () => {
  refreshReveal();
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
      await loadPost(slug);
      await buildArticleNavigation();
      refreshReveal();
    }
  },
);

onBeforeUnmount(() => {
  disconnectHeadingObserver();
});
</script>

<template>
  <div class="post-view print-post-view">
    <p v-if="loading" class="feedback print-feedback rv">文章页面正在展开……</p>

    <section v-else-if="error" class="print-page print-section post-empty-state">
      <div class="sec-hd rv">
        <span class="sec-hd__n">404</span>
        <h1 class="sec-hd__t">文章没有找到</h1>
        <div class="sec-hd__line"></div>
      </div>
      <p class="feedback print-feedback rv">{{ error }}</p>
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

      <header class="post-hero print-post-hero">
        <p class="section-label rv">{{ post.category || "Article" }}</p>
        <h1 class="rv" data-reveal-delay="60">{{ post.title }}</h1>
        <p v-if="post.excerpt" class="post-subtitle rv" data-reveal-delay="120">{{ post.excerpt }}</p>

        <div class="post-meta-row rv" data-reveal-delay="160">
          <span>{{ post.published_at || "未设置日期" }}</span>
          <span>{{ post.read_time }}</span>
        </div>

        <blockquote v-if="post.hero_quote" class="rv" data-reveal-delay="200">
          {{ post.hero_quote }}
        </blockquote>

        <div
          v-if="post.tags?.length"
          class="post-card-tags detail-tags print-detail-tags rv"
          data-reveal-delay="240"
        >
          <RouterLink
            v-for="tag in post.tags"
            :key="tag"
            :to="`/posts?tag=${encodeURIComponent(tag)}`"
            class="tag tag--code"
          >
            {{ tag }}
          </RouterLink>
        </div>
      </header>

      <div class="post-reading-layout">
        <aside v-if="tableOfContents.length" class="article-toc rv" data-reveal-delay="100">
          <div class="article-toc__head">
            <span>On this page</span>
            <strong>{{ String(tableOfContents.length).padStart(2, "0") }}</strong>
          </div>
          <nav aria-label="文章目录">
            <button
              v-for="(item, index) in tableOfContents"
              :key="item.id"
              type="button"
              :class="{ active: activeHeading === item.id, 'is-subsection': item.level === 3 }"
              :aria-current="activeHeading === item.id ? 'location' : undefined"
              @click="scrollToHeading(item.id)"
            >
              <span>{{ String(index + 1).padStart(2, "0") }}</span>
              <em>{{ item.label }}</em>
            </button>
          </nav>
          <p>阅读时，目录会跟随当前章节。</p>
        </aside>

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
      <span class="pg pg--r">— Article —</span>
    </article>

    <section v-if="relatedPosts.length" class="related-section print-related-section">
      <div class="sec-hd rv">
        <span class="sec-hd__n">Next</span>
        <h2 class="sec-hd__t">你也许还会想看</h2>
        <div class="sec-hd__line"></div>
      </div>

      <div class="g2e print-related-grid">
        <RouterLink
          v-for="(item, index) in relatedPosts"
          :key="item.slug"
          :to="`/posts/${item.slug}`"
          class="art print-article-strip rv"
          :data-reveal-delay="index * 70"
        >
          <span class="section-label">{{ item.category }}</span>
          <h3 class="art__t">{{ item.title }}</h3>
          <p class="art__p">{{ item.excerpt }}</p>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
