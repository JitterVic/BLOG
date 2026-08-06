<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import ArchiveLedger from "../components/posts/ArchiveLedger.vue";
import PostLatestList from "../components/posts/PostLatestList.vue";
import PostsToolbox from "../components/posts/PostsToolbox.vue";
import TagResultsGrid from "../components/posts/TagResultsGrid.vue";
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
  page,
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
let restoreSequence = 0;
let pendingRouteKey = "";
let routeSyncIncludePage = true;
let restoringPage = false;

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

function routeQueryKey(query = route.query) {
  return JSON.stringify({
    view: typeof query.view === "string" ? query.view : "",
    q: typeof query.q === "string" ? query.q : "",
    tag: typeof query.tag === "string" ? query.tag : "",
    page: typeof query.page === "string" ? query.page : "",
  });
}

function buildRouteQuery({ includePage = true } = {}) {
  const query = {};
  if (activeView.value !== "latest") query.view = activeView.value;
  if (searchQuery.value.trim()) query.q = searchQuery.value.trim();
  if (activeView.value === "tags" && selectedTag.value !== "全部") query.tag = selectedTag.value;
  if (includePage && activeView.value === "latest" && page.value > 1) {
    query.page = String(page.value);
  }
  return query;
}

function scheduleRouteSync({ includePage = true } = {}) {
  if (applyingRouteState) return;
  routeSyncIncludePage = includePage;
  if (querySyncTimer) window.clearTimeout(querySyncTimer);
  querySyncTimer = window.setTimeout(() => {
    querySyncTimer = 0;
    const query = buildRouteQuery({ includePage: routeSyncIncludePage });
    routeSyncIncludePage = true;
    pendingRouteKey = routeQueryKey(query);
    router.replace({ name: "posts", query });
  }, 180);
}

function requestedRoutePage() {
  const rawPage = Number.parseInt(route.query.page, 10);
  return Number.isFinite(rawPage) ? Math.min(Math.max(rawPage, 1), 100) : 1;
}

function listParams(requestedPage = 1) {
  const params = { sort: "latest" };
  const q = searchQuery.value.trim();
  if (q) params.q = q;
  if (activeView.value === "latest") {
    params.page = requestedPage;
    params.limit = PAGE_SIZE;
  }
  return params;
}

async function fetchList({ force = false, targetPage = 1 } = {}) {
  const params = listParams(1);
  const key = JSON.stringify(params);
  if (!force && targetPage === 1 && key === lastFetchedKey) return posts.value;
  lastFetchedKey = key;
  const restoreId = ++restoreSequence;
  restoringPage = true;
  try {
    await loadPosts(params);
    if (restoreId !== restoreSequence || targetPage <= 1 || activeView.value !== "latest") {
      return posts.value;
    }

    while (page.value < targetPage && hasMore.value) {
      await loadMore();
      if (restoreId !== restoreSequence) break;
    }
    return posts.value;
  } finally {
    if (restoreId === restoreSequence) {
      restoringPage = false;
      scheduleRouteSync();
    }
  }
}

function retryList() {
  return fetchList({ force: true, targetPage: requestedRoutePage() });
}

function scheduleReload() {
  if (reloadTimer) window.clearTimeout(reloadTimer);
  reloadTimer = window.setTimeout(() => {
    reloadTimer = 0;
    fetchList({ force: true, targetPage: 1 });
  }, 250);
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
    const currentRouteKey = routeQueryKey();
    if (currentRouteKey === pendingRouteKey) {
      pendingRouteKey = "";
      return;
    }
    applyRouteState().then(() => fetchList({ force: true, targetPage: requestedRoutePage() }));
  },
  { deep: true },
);

watch([activeView, selectedTag, searchQuery], () => {
  scheduleRouteSync({ includePage: false });
});

watch(page, () => {
  if (activeView.value === "latest" && !restoringPage) scheduleRouteSync();
});

// Typing is debounced; a discrete view switch reloads immediately.
watch(normalizedQuery, () => {
  scheduleReload();
});

watch(activeView, () => {
  if (applyingRouteState) return;
  if (reloadTimer) {
    window.clearTimeout(reloadTimer);
    reloadTimer = 0;
  }
  fetchList({ force: true, targetPage: 1 });
});

onMounted(async () => {
  ensureSite().catch(() => {});
  await applyRouteState();
  await fetchList({ force: true, targetPage: requestedRoutePage() });
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

      <PostsToolbox
        :view-options="VIEW_OPTIONS"
        :active-view="activeView"
        v-model:search-query="searchQuery"
        @set-view="setView"
        @clear-search="clearSearch"
      />

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

      <AsyncState
        v-if="error"
        :error="error"
        empty-message="请检查网络连接后重试。"
        @retry="retryList"
      />
      <div v-else-if="loading" class="posts-skeleton" aria-busy="true" aria-label="目录整理中">
        <div v-for="n in 4" :key="n" class="posts-skeleton__item">
          <div class="sk-line sk-line--sm"></div>
          <div class="sk-line sk-line--lg"></div>
          <div class="sk-line sk-line--md"></div>
        </div>
      </div>
      <AsyncState
        v-else-if="!visiblePosts.length"
        empty
        empty-title="没有找到文章"
        empty-message="请调整关键词或筛选条件后再试。"
      />

      <PostLatestList v-else-if="activeView === 'latest'" :posts="visiblePosts" />

      <ArchiveLedger v-else-if="activeView === 'archive'" :groups="groupedPosts" />

      <TagResultsGrid
        v-else
        :tags="tags"
        :selected-tag="selectedTag"
        :posts="visiblePosts"
        @select-tag="selectTag"
      />

      <div
        v-if="activeView === 'latest' && !loading && !error && hasMore"
        class="home-section-footer"
      >
        <button
          v-if="!loadMoreError"
          type="button"
          class="cover-button"
          :disabled="loadingMore"
          @click="loadMore"
        >
          {{ loadingMore ? "加载中……" : "加载更多" }}
        </button>
        <AsyncState
          v-else
          :error="loadMoreError"
          empty-message="请检查网络连接后重试。"
          @retry="loadMore"
        />
      </div>

      <span class="pg pg--r">— Article Index —</span>
    </section>
  </div>
</template>
