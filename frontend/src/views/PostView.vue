<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import css from "highlight.js/lib/languages/css";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import python from "highlight.js/lib/languages/python";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";

import { usePost } from "../composables/usePost";
import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";

hljs.registerLanguage("bash", bash);
hljs.registerLanguage("css", css);
hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("json", json);
hljs.registerLanguage("python", python);
hljs.registerLanguage("sql", sql);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("xml", xml);

const route = useRoute();
const { site, ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });
const articleBodyRef = ref(null);
const lightboxDialogRef = ref(null);
const lightboxImage = ref({ src: "", alt: "" });
const readingProgress = ref(0);
const tableOfContents = ref([]);
const activeHeading = ref("");
let headingObserver = null;
let progressFrame = null;
let enhancedElements = [];

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

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function disconnectHeadingObserver() {
  headingObserver?.disconnect();
  headingObserver = null;
}

function cleanupArticleEnhancements() {
  enhancedElements.forEach(({ element, event = "click", type, handler }) => {
    element.removeEventListener(event, handler);
    if (type === "button") element.remove();
  });
  enhancedElements = [];
}

function updateReadingProgress() {
  if (progressFrame) return;
  progressFrame = window.requestAnimationFrame(() => {
    progressFrame = null;
    const body = articleBodyRef.value;
    if (!body) {
      readingProgress.value = 0;
      return;
    }
    const bodyTop = body.getBoundingClientRect().top + window.scrollY;
    const readableHeight = Math.max(body.offsetHeight - window.innerHeight, 1);
    const current = window.scrollY - bodyTop;
    readingProgress.value = Math.min(1, Math.max(0, current / readableHeight));
  });
}

function openLightbox(image) {
  lightboxImage.value = {
    src: image.currentSrc || image.src,
    alt: image.alt || "文章图片",
  };
  const dialog = lightboxDialogRef.value;
  if (!dialog) return;
  if (typeof dialog.showModal === "function") dialog.showModal();
  else dialog.setAttribute("open", "");
}

function closeLightbox() {
  const dialog = lightboxDialogRef.value;
  if (!dialog) return;
  if (typeof dialog.close === "function") dialog.close();
  else dialog.removeAttribute("open");
}

function handleLightboxBackdrop(event) {
  if (event.target === lightboxDialogRef.value) closeLightbox();
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function enhanceArticleBody(body, headings) {
  cleanupArticleEnhancements();

  body.querySelectorAll("a[href]").forEach((anchor) => {
    const url = new URL(anchor.href, window.location.href);
    if (["http:", "https:"].includes(url.protocol) && url.origin !== window.location.origin) {
      anchor.target = "_blank";
      anchor.rel = "noopener";
    }
  });

  body.querySelectorAll("img").forEach((image) => {
    image.loading = "lazy";
    image.tabIndex = 0;
    image.setAttribute("role", "button");
    image.setAttribute("aria-label", `放大图片：${image.alt || "文章插图"}`);
    const openHandler = () => openLightbox(image);
    const keyHandler = (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      openLightbox(image);
    };
    image.addEventListener("click", openHandler);
    image.addEventListener("keydown", keyHandler);
    enhancedElements.push({ element: image, event: "click", handler: openHandler });
    enhancedElements.push({ element: image, event: "keydown", handler: keyHandler });
  });

  body.querySelectorAll("pre").forEach((pre) => {
    const code = pre.querySelector("code");
    if (!code || pre.querySelector(".code-copy-button")) return;
    hljs.highlightElement(code);
    pre.classList.add("has-copy-button");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "code-copy-button";
    button.textContent = "COPY";
    button.setAttribute("aria-label", "复制代码");
    const handler = async () => {
      try {
        await copyText(code.textContent || "");
        button.textContent = "COPIED";
      } catch {
        button.textContent = "FAILED";
      }
      window.setTimeout(() => { button.textContent = "COPY"; }, 1200);
    };
    button.addEventListener("click", handler);
    pre.appendChild(button);
    enhancedElements.push({ element: button, type: "button", handler });
  });

  headings.forEach((heading) => {
    if (heading.querySelector(":scope > .heading-anchor")) return;
    const anchor = document.createElement("a");
    anchor.className = "heading-anchor";
    anchor.href = `#${heading.id}`;
    anchor.textContent = "#";
    anchor.setAttribute("aria-label", `复制或跳转到章节：${heading.textContent?.trim() || heading.id}`);
    const handler = () => {
      history.replaceState(null, "", `#${heading.id}`);
    };
    anchor.addEventListener("click", handler);
    heading.appendChild(anchor);
    enhancedElements.push({ element: anchor, type: "button", handler });
  });
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

  enhanceArticleBody(body, headings);
  updateReadingProgress();

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
  window.addEventListener("scroll", updateReadingProgress, { passive: true });
  window.addEventListener("resize", updateReadingProgress);

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
  window.removeEventListener("scroll", updateReadingProgress);
  window.removeEventListener("resize", updateReadingProgress);
  if (progressFrame) window.cancelAnimationFrame(progressFrame);
  closeLightbox();
  disconnectHeadingObserver();
  cleanupArticleEnhancements();
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

        <figure v-if="post.cover_image" class="post-cover rv" data-reveal-delay="180">
          <img
            :src="post.cover_image"
            :alt="post.title"
            loading="lazy"
            @error="(event) => event.target.closest('figure').classList.add('is-broken')"
          >
        </figure>

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

      <nav v-if="previousPost || nextPost" class="post-sequence-nav rv" aria-label="上一篇和下一篇">
        <RouterLink
          v-if="previousPost"
          :to="`/posts/${previousPost.slug}`"
          class="post-sequence-link post-sequence-link--previous"
        >
          <span>← Previous</span>
          <strong>{{ previousPost.title }}</strong>
        </RouterLink>
        <span v-else class="post-sequence-placeholder"></span>
        <RouterLink
          v-if="nextPost"
          :to="`/posts/${nextPost.slug}`"
          class="post-sequence-link post-sequence-link--next"
        >
          <span>Next →</span>
          <strong>{{ nextPost.title }}</strong>
        </RouterLink>
      </nav>      <span class="pg pg--r">— Article —</span>
    </article>

    <dialog
      ref="lightboxDialogRef"
      class="article-lightbox"
      aria-label="文章图片预览"
      @click="handleLightboxBackdrop"
      @cancel.prevent="closeLightbox"
    >
      <button type="button" class="article-lightbox__close" aria-label="关闭图片预览" @click="closeLightbox">
        CLOSE ×
      </button>
      <figure>
        <img :src="lightboxImage.src" :alt="lightboxImage.alt">
        <figcaption v-if="lightboxImage.alt">{{ lightboxImage.alt }}</figcaption>
      </figure>
    </dialog>

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
