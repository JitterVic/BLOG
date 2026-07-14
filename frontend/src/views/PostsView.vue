<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { usePosts } from "../composables/usePosts";
import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";

const VIEW_OPTIONS = [
  { id: "latest", label: "最新文章", english: "Latest" },
  { id: "archive", label: "归档查找", english: "Archive" },
  { id: "tags", label: "标签筛选", english: "Tags" },
];

const PAGE_SIZE = 10;

const {
  posts,
  error,
  loading,
  loadingMore,
  loadMoreError,
  total,
  hasMore,
  loadPosts,
  loadMore,
} = usePosts({ errorMessage: "文章目录加载失败，请稍后再试。" });

const route = useRoute();
const router = useRouter();
const { site, ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });
const activeView = ref("latest");
const searchQuery = ref("");
const selectedTag = ref("全部");
let applyingRouteState = false;
let querySyncTimer = 0;
let reloadTimer = 0;
let lastFetchedKey = "";

const normalizedQuery = computed(() => searchQuery.value.trim().toLowerCase());
const tags = computed(() => {
  const siteTags = [...(site.value?.tags || [])].sort((a, b) => a.localeCompare(b, "zh-CN"));
  return ["全部", ...siteTags];
});

const visiblePosts = computed(() => {
  if (activeView.value !== "tags" || selectedTag.value === "全部") {
    return posts.value;
  }

  return posts.value.filter((post) => post.tags?.includes(selectedTag.value));
});

const groupedPosts = computed(() => {
  const groups = new Map();
  for (const post of visiblePosts.value) {
    const year = (post.published_at || "未归档").slice(0, 4);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(post);
  }
  return Array.from(groups.entries());
});

const resultLabel = computed(() => {
  if (activeView.value === "tags" && selectedTag.value !== "全部") {
    return `${selectedTag.value} · ${visiblePosts.value.length} 篇`;
  }
  const count = activeView.value === "latest" ? total.value : visiblePosts.value.length;
  if (normalizedQuery.value) {
    return `搜索结果 · ${count} 篇`;
  }
  return `共 ${count} 篇文章`;
});

function setView(view) {
  activeView.value = view;
  if (view !== "tags") selectedTag.value = "全部";
}

function selectTag(tag) {
  activeView.value = "tags";
  selectedTag.value = tag;
}

function clearSearch() {
  searchQuery.value = "";
}

function clearAllFilters() {
  searchQuery.value = "";
  selectedTag.value = "全部";
}

function buildRouteQuery() {
  const query = {};
  if (activeView.value !== "latest") query.view = activeView.value;
  if (searchQuery.value.trim()) query.q = searchQuery.value.trim();
  if (activeView.value === "tags" && selectedTag.value !== "全部") query.tag = selectedTag.value;
  return query;
}

function scheduleRouteSync() {
  if (applyingRouteState) return;
  if (querySyncTimer) window.clearTimeout(querySyncTimer);
  querySyncTimer = window.setTimeout(() => {
    querySyncTimer = 0;
    router.replace({ name: "posts", query: buildRouteQuery() });
  }, 180);
}

function listParams() {
  const params = { sort: "latest" };
  const q = searchQuery.value.trim();
  if (q) params.q = q;
  if (activeView.value === "latest") {
    params.page = 1;
    params.limit = PAGE_SIZE;
  }
  return params;
}

function fetchList({ force = false } = {}) {
  const params = listParams();
  const key = JSON.stringify(params);
  if (!force && key === lastFetchedKey) return;
  lastFetchedKey = key;
  loadPosts(params);
}

function scheduleReload() {
  if (reloadTimer) window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => {
    reloadTimer = 0;
    fetchList();
  }, 250);
}

function displayDate(value) {
  return value || "未设置日期";
}

function shortDate(value) {
  if (!value) return "--.--";
  const [, month, day] = value.split("-");
  return month && day ? `${month}-${day}` : value;
}

async function applyRouteState() {
  applyingRouteState = true;
  const requestedView = typeof route.query.view === "string" ? route.query.view : "";
  const tag = typeof route.query.tag === "string" ? route.query.tag.trim() : "";
  const query = typeof route.query.q === "string" ? route.query.q : "";
  const validView = VIEW_OPTIONS.some((item) => item.id === requestedView)
    ? requestedView
    : tag
      ? "tags"
      : "latest";

  activeView.value = validView;
  searchQuery.value = query;
  selectedTag.value = validView === "tags" && tag ? tag : "全部";
  await nextTick();
  applyingRouteState = false;
}

watch([visiblePosts, activeView, loading], () => {
  refreshReveal();
});

watch(
  () => route.query,
  () => {
    applyRouteState();
  },
  { deep: true },
);

watch([activeView, selectedTag, searchQuery], () => {
  scheduleRouteSync();
});

// Typing is debounced; a discrete view switch reloads immediately.
watch(normalizedQuery, () => {
  scheduleReload();
});

watch(activeView, () => {
  if (reloadTimer) {
    window.clearTimeout(reloadTimer);
    reloadTimer = 0;
  }
  fetchList();
});

onMounted(async () => {
  ensureSite().catch(() => {});
  await applyRouteState();
  fetchList({ force: true });
  refreshReveal();
});

onBeforeUnmount(() => {
  if (querySyncTimer) window.clearTimeout(querySyncTimer);
  if (reloadTimer) window.clearTimeout(reloadTimer);
});
</script>

<template>
  <div class="content-view print-subpage unified-posts-page">
    <section class="print-page print-section">
      <p class="posts-chapter-label rv">Catalog of Issues</p>
      <div class="sec-hd rv">
        <span class="sec-hd__n">02</span>
        <h1 class="sec-hd__t">文章 Articles</h1>
        <div class="sec-hd__line"></div>
      </div>

      <div class="article-toolbox rv">
        <div class="article-view-switch" role="tablist" aria-label="文章目录视图">
          <button
            v-for="item in VIEW_OPTIONS"
            :key="item.id"
            type="button"
            class="article-view-button"
            :class="{ active: activeView === item.id }"
            role="tab"
            :aria-selected="activeView === item.id"
            @click="setView(item.id)"
          >
            <strong>{{ item.label }}</strong>
            <span>{{ item.english }}</span>
          </button>
        </div>

        <label class="article-search">
          <span class="article-search__label">Search the issue</span>
          <span class="article-search__field">
            <input
              v-model="searchQuery"
              type="search"
              placeholder="搜索标题、摘要或标签"
              autocomplete="off"
            >
            <button v-if="searchQuery" type="button" @click="clearSearch">清除</button>
          </span>
        </label>
      </div>

      <div class="article-directory-meta rv" aria-live="polite">
        <span>{{ resultLabel }}</span>
        <button
          v-if="searchQuery || selectedTag !== '全部'"
          type="button"
          @click="clearAllFilters"
        >
          清除筛选
        </button>
      </div>

      <p v-if="error" class="feedback print-feedback rv">{{ error }}</p>
      <div v-else-if="loading" class="posts-skeleton" aria-busy="true" aria-label="目录整理中">
        <div v-for="n in 4" :key="n" class="posts-skeleton__item">
          <div class="sk-line sk-line--sm"></div>
          <div class="sk-line sk-line--lg"></div>
          <div class="sk-line sk-line--md"></div>
        </div>
      </div>
      <p v-else-if="!visiblePosts.length" class="feedback print-feedback rv">
        没有找到符合条件的文章，请调整关键词或筛选条件。
      </p>

      <div v-else-if="activeView === 'latest'" class="article-list print-article-list unified-latest-list">
        <RouterLink
          v-for="(post, index) in visiblePosts"
          :key="post.slug"
          :to="`/posts/${post.slug}`"
          class="article-item print-list-item rv"
          :class="{ 'article-item--has-cover': !!post.cover_image }"
          :data-reveal-delay="Math.min(index, 8) * 45"
        >
          <img
            v-if="post.cover_image"
            class="article-item__thumb"
            :src="post.cover_image"
            alt=""
            loading="lazy"
            @error="(event) => event.target.classList.add('is-broken')"
          >
          <div class="article-meta">
            <span>{{ displayDate(post.published_at) }}</span>
            <span>{{ post.read_time }}</span>
          </div>
          <h2>{{ post.title }}</h2>
          <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
          <div class="post-card-tags list-tags">
            <span v-for="tag in post.tags" :key="tag" class="tag tag--code">{{ tag }}</span>
          </div>
        </RouterLink>
      </div>

      <div v-else-if="activeView === 'archive'" class="print-year-ledger unified-archive-view">
        <section
          v-for="([year, items], index) in groupedPosts"
          :key="year"
          class="archive print-year-block rv"
          :data-reveal-delay="index * 60"
        >
          <div class="archive__year">
            <span>{{ year }}</span>
            <strong>{{ items.length }} 篇</strong>
          </div>
          <ul class="archive__list">
            <li v-for="post in items" :key="post.slug" class="archive__li">
              <span class="archive__date">{{ shortDate(post.published_at) }}</span>
              <RouterLink :to="`/posts/${post.slug}`" class="archive__title">{{ post.title }}</RouterLink>
              <span class="archive__tags">
                <span v-for="tag in post.tags?.slice(0, 2)" :key="tag" class="tag tag--code">{{ tag }}</span>
              </span>
            </li>
          </ul>
          <div v-if="index < groupedPosts.length - 1" class="orn">✦</div>
        </section>
      </div>

      <div v-else class="unified-tags-view">
        <aside class="tag-filter-row print-tag-cloud rv" aria-label="标签筛选">
          <button
            v-for="tag in tags"
            :key="tag"
            type="button"
            class="tag-filter-button tag"
            :class="{ active: selectedTag === tag, 'tag--hot': selectedTag === tag }"
            @click="selectTag(tag)"
          >
            {{ tag }}
          </button>
        </aside>

        <div class="g2e print-tag-results">
          <RouterLink
            v-for="(post, index) in visiblePosts"
            :key="post.slug"
            :to="`/posts/${post.slug}`"
            class="art print-article-strip rv"
            :data-reveal-delay="Math.min(index, 6) * 50"
          >
            <div class="art__cat">{{ post.category || "Article" }}</div>
            <h2 class="art__t art__t--lg">{{ post.title }}</h2>
            <p class="art__p">{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
            <div class="art__meta">
              <span>{{ displayDate(post.published_at) }}</span>
              <span>{{ post.read_time }}</span>
            </div>
          </RouterLink>
        </div>
      </div>

      <div
        v-if="activeView === 'latest' && !loading && !error && hasMore"
        class="home-section-footer"
      >
        <button type="button" class="cover-button" :disabled="loadingMore" @click="loadMore">
          {{ loadingMore ? "加载中……" : "加载更多" }}
        </button>
        <p v-if="loadMoreError" class="feedback print-feedback" role="alert">{{ loadMoreError }}</p>
      </div>

      <span class="pg pg--r">— Article Index —</span>
    </section>
  </div>
</template>
