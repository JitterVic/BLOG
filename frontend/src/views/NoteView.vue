<script setup>
// 余笺详情（DESIGN.md §5.3）：复用文章页版面（36em 卷 + ≥1100px 批注栏）。
// 右栏放余笺元信息与同类型近期余笺；正文下方是规整的 external_url 作品外链信息条。

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import ImageLightbox from "../components/post/ImageLightbox.vue";
import ReadingTools from "../components/post/ReadingTools.vue";
import { useLightbox } from "../composables/useLightbox";
import { setPageMeta } from "../composables/usePageMeta";
import { useTitleMorph } from "../composables/useTitleMorph";
import { shortDate } from "../composables/useFormat";
import { enhanceArticleBody } from "../lib/articleEnhancer";
import { getNote, getNotes } from "../services/api";

const route = useRoute();
const { handleOpen } = useTitleMorph();
const note = ref(null);
const loading = ref(false);
const error = ref("");

const noteContentRef = ref(null);
const { dialogRef, lightboxImage, open: openLightbox, close: closeLightbox, handleBackdropClick } =
  useLightbox();
let cleanupEnhancements = null;

const relatedNotes = ref([]);
let relatedController = null;

const externalHost = computed(() => {
  const url = note.value?.external_url;
  if (!url) return "";
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
});

function teardownNote() {
  closeLightbox();
  cleanupEnhancements?.();
  cleanupEnhancements = null;
  relatedController?.abort();
}

async function enhanceNoteContent() {
  await nextTick();
  cleanupEnhancements?.();
  if (!noteContentRef.value) return;
  const headings = Array.from(noteContentRef.value.querySelectorAll(".prose h2[id], .prose h3[id]"));
  cleanupEnhancements = enhanceArticleBody(noteContentRef.value, headings, { openLightbox });
}

async function loadRelatedNotes(current) {
  relatedController?.abort();
  relatedController = new AbortController();
  try {
    const result = await getNotes({ type: current?.type || "", limit: 6, signal: relatedController.signal });
    relatedNotes.value = (Array.isArray(result?.items) ? result.items : [])
      .filter((item) => item?.slug !== current?.slug)
      .slice(0, 5);
  } catch {
    // 右栏同类余笺加载失败不影响正文
    relatedNotes.value = [];
  }
}

async function load() {
  teardownNote();
  loading.value = true;
  error.value = "";
  try {
    note.value = await getNote(route.params.slug);
    setPageMeta({ title: `${note.value.title} · 余笺 · 至知`, description: note.value.excerpt || "至知余笺。" });
    await enhanceNoteContent();
    loadRelatedNotes(note.value);
  } catch (err) {
    note.value = null;
    error.value = err?.code === "NOT_FOUND" ? "这则余笺不存在，或仍是草稿。" : "余笺暂时无法加载，请稍后重试。";
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => route.params.slug, load);
onBeforeUnmount(teardownNote);
</script>

<template>
  <div class="note-view">
    <AsyncState v-if="loading" loading variant="post" loading-message="正在加载…" />
    <section v-else-if="error" class="state" role="alert">
      <h1 class="state__title">找不到这则余笺</h1>
      <p class="state__text">{{ error }}</p>
      <div class="state__actions state__actions--row">
        <RouterLink class="text-link" to="/notes">返回余笺</RouterLink>
        <RouterLink class="text-link" to="/">回首页</RouterLink>
      </div>
    </section>
    <article v-else-if="note" ref="noteContentRef" class="article note-article">
      <header class="article-head">
        <p class="article-head__category">
          <RouterLink class="text-link" :to="{ name: 'notes', query: note.type ? { type: note.type } : {} }">
            {{ note.type_label }}
          </RouterLink>
        </p>
        <h1 class="article-head__title">{{ note.title }}</h1>
        <p v-if="note.excerpt" class="article-head__excerpt">{{ note.excerpt }}</p>
        <div class="article-head__meta">
          <p class="article-head__meta-info">
            <time :datetime="note.published_at">{{ note.published_at }}</time>
          </p>
          <ReadingTools />
        </div>
      </header>
      <section v-if="note.html_content" class="article-body prose" v-html="note.html_content"></section>
      <div v-if="note.media?.length" class="note-media">
        <img
          v-for="item in note.media"
          :key="item.url || item"
          :src="item.url || item"
          :alt="item.alt || note.title"
          loading="lazy"
        >
      </div>
      <aside v-if="note.external_url" class="note-ext-bar" aria-label="外部链接">
        <div class="note-ext-bar__info">
          <span class="note-ext-bar__label">关联地址</span>
          <span class="note-ext-bar__host">{{ externalHost }}</span>
        </div>
        <a class="btn" :href="note.external_url" target="_blank" rel="noopener noreferrer">
          访问链接 ↗
        </a>
      </aside>
      <aside class="article-side" aria-label="余笺信息与同类余笺">
        <section class="side-block">
          <header class="side-block__head">
            <h2 class="side-block__title">余笺信息</h2>
          </header>
          <dl class="note-side-meta">
            <dt>类型</dt>
            <dd>
              <RouterLink class="text-link" :to="{ name: 'notes', query: note.type ? { type: note.type } : {} }">
                {{ note.type_label }}
              </RouterLink>
            </dd>
            <dt>发布</dt>
            <dd><time :datetime="note.published_at">{{ note.published_at }}</time></dd>
            <template v-if="externalHost">
              <dt>关联</dt>
              <dd>{{ externalHost }}</dd>
            </template>
          </dl>
        </section>
        <section v-if="relatedNotes.length" class="side-block">
          <header class="side-block__head">
            <h2 class="side-block__title">同类余笺</h2>
          </header>
          <ul class="side-compact-list">
            <li v-for="item in relatedNotes" :key="item.slug">
              <p class="side-compact-list__meta">
                <time :datetime="item.published_at">{{ shortDate(item.published_at) }}</time>
                <span v-if="item.type_label">{{ item.type_label }}</span>
              </p>
              <RouterLink
                class="side-compact-list__link"
                :to="{ name: 'note', params: { slug: item.slug } }"
                @click="handleOpen($event, { name: 'note', params: { slug: item.slug } })"
              >{{ item.title }}</RouterLink>
            </li>
          </ul>
        </section>
      </aside>
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
