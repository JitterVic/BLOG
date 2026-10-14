<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import ArchiveLedger from "../components/posts/ArchiveLedger.vue";
import PostsToolbox from "../components/posts/PostsToolbox.vue";
import { usePosts } from "../composables/usePosts";
import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";

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

// 标签筛选在服务端完成（`tag` 查询参数），因此翻页与筛选可以并存，
// 而不必像以前那样为了客户端过滤一次性取回全部文章。
const visiblePosts = computed(() => posts.value);

const groupedPosts = computed(() => {
  const groups = new Map();
  for (const post of visiblePosts.value) {
    const year = (post.published_at || "未归档").slice(0, 4);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(post);
  }
  return Array.from(groups.entries());
});

const latestSlug = computed(() => posts.value[0]?.slug || "");

const resultLabel = computed(() => {
  const count = total.value;
  if (normalizedQuery.value) {
    return `搜索结果 · ${count} 篇`;
  }
  if (selectedTag.value !== "全部") {
    return `${selectedTag.value} · ${count} 篇`;
  }
  return `共 ${count} 篇文章`;
});

function selectTag(tag) {
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
    q: typeof query.q === "string" ? query.q : "",
    tag: typeof query.tag === "string" ? query.tag : "",
    page: typeof query.page === "string" ? query.page : "",
  });
}

function buildRouteQuery({ includePage = true } = {}) {
  const query = {};
  if (searchQuery.value.trim()) query.q = searchQuery.value.trim();
  if (selectedTag.value !== "全部") query.tag = selectedTag.value;
  if (includePage && page.value > 1) {
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
  const params = { sort: "latest", page: requestedPage, limit: PAGE_SIZE };
  const q = searchQuery.value.trim();
  if (q) params.q = q;
  if (selectedTag.value !== "全部") params.tag = selectedTag.value;
  return params;
}

async function fetchList({ force = false, targetPage = 1 } = {}) {
  const params = listParams(1);
  const key = JSON.stringify(params);
  if (!force && key === lastFetchedKey) return posts.value;
  lastFetchedKey = key;
  const restoreId = ++restoreSequence;
  restoringPage = true;
  try {
    await loadPosts(params);
    if (restoreId !== restoreSequence || targetPage <= 1) {
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
  const tag = typeof route.query.tag === "string" ? route.query.tag.trim() : "";
  const query = typeof route.query.q === "string" ? route.query.q : "";
  // 旧的 `?view=tags&tag=x` 链接继续可用：视图维度已取消，tag 直接当作筛选条件。
  const isValidTag = tag && tags.value.includes(tag);

  searchQuery.value = query;
  selectedTag.value = isValidTag ? tag : "全部";
  await nextTick();
  applyingRouteState = false;
}

watch([visiblePosts, loading], () => {
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

watch([selectedTag, searchQuery], () => {
  scheduleRouteSync({ includePage: false });
});

watch(page, () => {
  if (!restoringPage) scheduleRouteSync();
});

// Typing is debounced; a discrete tag switch reloads immediately.
watch(normalizedQuery, () => {
  scheduleReload();
});

watch(selectedTag, () => {
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
        <h1 class="sec-hd__t">文章 Articles</h1>
        <div class="sec-hd__line"></div>
      </div>

      <PostsToolbox
        :tags="tags"
        :selected-tag="selectedTag"
        v-model:search-query="searchQuery"
        @set-tag="selectTag"
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
      <AsyncState
        v-else-if="loading"
        loading
        variant="posts"
        loading-message="目录正在整理装订……"
      />
      <AsyncState
        v-else-if="!visiblePosts.length"
        empty
        empty-title="没有找到文章"
        empty-message="请调整关键词或筛选条件后再试。"
      />

      <ArchiveLedger v-else :groups="groupedPosts" :latest-slug="latestSlug" />

      <div
        v-if="!loading && !error && hasMore"
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
