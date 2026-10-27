<script setup>
// 文章列表（DESIGN.md §5.2）：按年份分组的编年索引 + 栏目筛选 + 搜索。
// 筛选走服务端 category（左栏 / 窄屏栏目条），搜索走 q —— 筛选与翻页可以并存。
// URL 是唯一状态源（cat / q / page 可分享、可后退）；视图内只做防抖同步。
// 三栏书案：右栏是年份跳表 + 全站标签索引；搜索态下右栏顶部联动展示匹配的余笺。

import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import PostRow from "../components/PostRow.vue";
import { useMediaQuery } from "../composables/useMediaQuery";
import { usePosts } from "../composables/usePosts";
import { useSite } from "../composables/useSite";
import { groupByYear } from "../lib/postGroups";
import { getNotes, isRequestAbort } from "../services/api";

const PAGE_SIZE = 20;

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
} = usePosts({ errorMessage: "文章没能加载出来。检查网络后重试。" });

const route = useRoute();
const router = useRouter();
const { site, ensureSite } = useSite();

const searchQuery = ref("");
const selectedCategory = ref("全部");
const loadedAnnouncement = ref("");
let applyingRouteState = false;
let querySyncTimer = 0;
let reloadTimer = 0;
let lastFetchedKey = "";
let restoreSequence = 0;
let pendingRouteKey = "";
let routeSyncIncludePage = true;
let restoringPage = false;
let loadedTotalBefore = 0;

// 栏目条只在窄屏出场（≥1100px 左栏在场）；渲染由 CSS 收管
const wideViewport = useMediaQuery("(max-width: 1099px)");
const showCatStrip = computed(() => wideViewport.value && categories.value.length > 0);

const normalizedQuery = computed(() => searchQuery.value.trim().toLowerCase());
const highlightTerm = computed(() => (route.query.q ? String(route.query.q) : ""));

const categories = computed(() => {
  const raw = site.value?.categories || [];
  return raw
    .map((item) =>
      typeof item === "string"
        ? { name: item, total: 0 }
        : {
            name: item?.name || "",
            total: Number(item?.total ?? item?.count) || 0,
          },
    )
    .filter((item) => item.name);
});

const groupedPosts = computed(() => groupByYear(posts.value));
const years = computed(() => groupedPosts.value.map(([year]) => year));

const siteTags = computed(() => {
  const tags = site.value?.tags;
  return Array.isArray(tags) ? tags.filter((tag) => typeof tag === "string") : [];
});

const subtitle = computed(() => {
  const q = searchQuery.value.trim();
  if (q) return `搜索「${q}」，找到 ${total.value} 篇`;
  if (selectedCategory.value !== "全部") return `栏目：${selectedCategory.value}，共 ${total.value} 篇`;
  return `共 ${total.value} 篇`;
});

const isSearchState = computed(() => Boolean(searchQuery.value.trim()));

/* 搜索态下的余笺联动（§5.2）：q 非空时并行拉一次余笺，客户端按标题/摘要/类型匹配 */
const notesForSearch = ref([]);
let notesController = null;

async function loadNotesForSearch() {
  notesController?.abort();
  if (!isSearchState.value) {
    notesForSearch.value = [];
    return;
  }
  notesController = new AbortController();
  try {
    const result = await getNotes({ limit: 50, signal: notesController.signal });
    notesForSearch.value = Array.isArray(result?.items) ? result.items : [];
  } catch (err) {
    if (!isRequestAbort(err)) notesForSearch.value = [];
  }
}

const matchedNotes = computed(() => {
  const q = normalizedQuery.value;
  if (!q) return [];
  return notesForSearch.value
    .filter((note) =>
      `${note?.title || ""}\n${note?.excerpt || ""}\n${note?.type_label || ""}`
        .toLowerCase()
        .includes(q),
    )
    .slice(0, 5);
});

/** 余笺标题的命中词分段（不做 v-html，文本拼接），命中段套 .marker。 */
function noteTitleSegments(title) {
  const value = String(title || "");
  const needle = normalizedQuery.value;
  if (!needle || !value) return [{ text: value, mark: false }];
  const lower = value.toLowerCase();
  const parts = [];
  let cursor = 0;
  let index = lower.indexOf(needle);
  while (index !== -1) {
    if (index > cursor) parts.push({ text: value.slice(cursor, index), mark: false });
    parts.push({ text: value.slice(index, index + needle.length), mark: true });
    cursor = index + needle.length;
    index = lower.indexOf(needle, cursor);
  }
  if (cursor < value.length) parts.push({ text: value.slice(cursor), mark: false });
  return parts;
}

/* 空态文案（§6.7）：搜索 / 栏目 / 全站三种口径分开说；文章落空但余笺命中时指路右栏 */
const emptyMessage = computed(() => {
  const q = searchQuery.value.trim();
  if (q) {
    if (!posts.value.length && matchedNotes.value.length) {
      return `没有找到「${q}」相关的文章，但在右侧找到了 ${matchedNotes.value.length} 则相关余笺。`;
    }
    return `没有找到「${q}」相关的文章。换个关键词试试。`;
  }
  if (selectedCategory.value !== "全部") return `「${selectedCategory.value}」下还没有文章。可以看看其他栏目。`;
  return "还没有文章。";
});

function clearSearch() {
  searchQuery.value = "";
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function jumpToYear(year) {
  const heading = document.getElementById(`year-${year}`);
  if (!heading) return;
  heading.scrollIntoView({
    behavior: prefersReducedMotion() ? "auto" : "smooth",
    block: "start",
  });
}

function routeQueryKey(query = route.query) {
  return JSON.stringify({
    q: typeof query.q === "string" ? query.q : "",
    cat: typeof query.cat === "string" ? query.cat : "",
    page: typeof query.page === "string" ? query.page : "",
  });
}

function buildRouteQuery({ includePage = true } = {}) {
  const query = {};
  if (searchQuery.value.trim()) query.q = searchQuery.value.trim();
  if (selectedCategory.value !== "全部") query.cat = selectedCategory.value;
  if (includePage && page.value > 1) query.page = String(page.value);
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
  if (selectedCategory.value !== "全部") params.category = selectedCategory.value;
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

/** 「再加载 N 篇」：完成后用 aria-live 播报「已加载 N 篇」（§5.2） */
async function loadMoreAndAnnounce() {
  loadedTotalBefore = posts.value.length;
  await loadMore();
  const added = posts.value.length - loadedTotalBefore;
  if (added > 0) loadedAnnouncement.value = `已加载 ${added} 篇`;
}

async function applyRouteState() {
  applyingRouteState = true;
  const rawCat = typeof route.query.cat === "string" ? route.query.cat.trim() : "";
  const query = typeof route.query.q === "string" ? route.query.q : "";
  searchQuery.value = query;
  // 栏目取值缺省（含空串）都落回「全部」，否则「全部」这个选项永远不成立
  selectedCategory.value = rawCat || "全部";
  await nextTick();
  applyingRouteState = false;
}

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

watch([selectedCategory, searchQuery], () => {
  scheduleRouteSync({ includePage: false });
});

watch(page, () => {
  if (!restoringPage) scheduleRouteSync();
});

// 输入搜索词走防抖；从文章页点标签 / 左栏搜索跳进来属于「初次进入」，已由 route state 取数
watch(normalizedQuery, () => {
  loadNotesForSearch();
  if (applyingRouteState) return;
  scheduleReload();
});

watch(selectedCategory, () => {
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
  loadNotesForSearch();
});

onBeforeUnmount(() => {
  if (querySyncTimer) window.clearTimeout(querySyncTimer);
  if (reloadTimer) window.clearTimeout(reloadTimer);
  notesController?.abort();
});
</script>

<template>
  <div class="posts-view">
    <header class="posts-head">
      <h1>文章</h1>
      <p class="posts-head__sub">
        <span>{{ subtitle }}</span>
        <button v-if="isSearchState" type="button" class="text-btn" @click="clearSearch">清除</button>
      </p>
    </header>

    <!-- 窄屏栏目条（≥1100px 由左栏承担，CSS 隐去）-->
    <nav v-if="showCatStrip" class="cat-strip" aria-label="栏目">
      <RouterLink
        class="cat-strip__link"
        :to="{ name: 'posts' }"
        :aria-current="selectedCategory === '全部' ? 'page' : undefined"
      >
        <span class="marker-sweep" :class="{ 'is-on': selectedCategory === '全部' }">全部</span>
      </RouterLink>
      <RouterLink
        v-for="category in categories"
        :key="category.name"
        class="cat-strip__link"
        :to="{ name: 'posts', query: { cat: category.name } }"
        :aria-current="selectedCategory === category.name ? 'page' : undefined"
      >
        <span class="marker-sweep" :class="{ 'is-on': selectedCategory === category.name }">{{ category.name }}</span>
      </RouterLink>
    </nav>

    <div class="page-grid">
      <div class="page-grid__main">
        <AsyncState
          v-if="error"
          :error="error"
          empty-message="请检查网络后重试。"
          @retry="retryList"
        />
        <AsyncState
          v-else-if="loading && !posts.length"
          loading
          variant="rows"
          loading-message="正在加载…"
        />
        <section v-else-if="!posts.length" class="state" role="status" aria-live="polite">
          <p class="state__text">{{ emptyMessage }}</p>
          <div v-if="isSearchState" class="state__actions">
            <button type="button" class="text-btn" @click="clearSearch">清除搜索</button>
          </div>
          <div v-else-if="selectedCategory !== '全部'" class="state__actions">
            <RouterLink class="text-link" :to="{ name: 'posts' }">全部文章</RouterLink>
          </div>
        </section>

        <!-- 已有数据再次筛选时保留列表 DOM，只降不透明度，防止视口高度骤降（§5.2） -->
        <div v-else class="posts-list" :class="{ 'list-refreshing': loading }">
          <Transition name="list-swap">
            <div :key="`${selectedCategory}-${normalizedQuery}`">
              <section
                v-for="[year, groupPosts] in groupedPosts"
                :key="year"
                class="year-group"
                :aria-label="`${year} 年`"
              >
                <h2 :id="`year-${year}`" class="year-group__head">{{ year }}</h2>
                <PostRow
                  v-for="post in groupPosts"
                  :key="post.slug"
                  :post="post"
                  date-format="short"
                  :highlight="highlightTerm"
                />
              </section>

              <p class="sr-only" aria-live="polite">{{ loadedAnnouncement }}</p>

              <div v-if="hasMore" class="posts-more">
                <button
                  v-if="!loadMoreError"
                  type="button"
                  class="btn"
                  :disabled="loadingMore"
                  @click="loadMoreAndAnnounce"
                >
                  {{ loadingMore ? "加载中…" : `再加载 ${PAGE_SIZE} 篇` }}
                </button>
                <AsyncState
                  v-else
                  :error="loadMoreError"
                  compact
                  retry-label="重试"
                  empty-message="请检查网络后重试。"
                  @retry="loadMoreAndAnnounce"
                />
              </div>
              <p v-else-if="posts.length" class="posts-end">已经到底了，共 {{ total }} 篇。</p>
            </div>
          </Transition>
        </div>
      </div>

      <!-- 右辅栏：搜索态余笺联动 + 年份跳表 + 标签索引 -->
      <aside class="page-grid__side page-grid__side--sticky posts-side">
        <section v-if="isSearchState" class="side-block" aria-label="相关余笺">
          <header class="side-block__head">
            <h2 class="side-block__title">相关余笺</h2>
            <span class="side-block__sub">{{ matchedNotes.length }}</span>
          </header>
          <ul v-if="matchedNotes.length" class="side-compact-list">
            <li v-for="note in matchedNotes" :key="note.slug">
              <p class="side-compact-list__meta">
                <time :datetime="note.published_at">{{ note.published_at }}</time>
                <span v-if="note.type_label">{{ note.type_label }}</span>
              </p>
              <RouterLink
                class="side-compact-list__link"
                :to="{ name: 'note', params: { slug: note.slug } }"
              >
                <template v-for="(seg, i) in noteTitleSegments(note.title)" :key="i">
                  <mark v-if="seg.mark" class="marker">{{ seg.text }}</mark>
                  <template v-else>{{ seg.text }}</template>
                </template>
              </RouterLink>
            </li>
          </ul>
          <p v-else class="side-block__empty">没有匹配的余笺。</p>
        </section>

        <section v-if="years.length" class="side-block" aria-label="年份索引">
          <header class="side-block__head">
            <h2 class="side-block__title">年份</h2>
          </header>
          <nav class="year-index" aria-label="按年份跳转">
            <button
              v-for="year in years"
              :key="year"
              type="button"
              class="year-index__link"
              @click="jumpToYear(year)"
            >{{ year }}</button>
          </nav>
        </section>

        <section v-if="siteTags.length" class="side-block" aria-label="标签索引">
          <header class="side-block__head">
            <h2 class="side-block__title">标签</h2>
            <span class="side-block__sub">{{ siteTags.length }}</span>
          </header>
          <div class="tag-index">
            <RouterLink
              v-for="tag in siteTags"
              :key="tag"
              class="tag-index__link"
              :class="{ marker: tag === highlightTerm }"
              :to="{ name: 'posts', query: { q: tag } }"
            >{{ tag }}</RouterLink>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>
