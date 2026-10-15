// 文章页左侧清单的数据源。
//
// 为什么必须是模块级单例：`PostView` 用 `:key="viewRoute.fullPath"` 强制重建，
// 换一篇就换一个组件实例。若把列表放在组件里，读者每从清单点一篇都会重新发一次
// 同栏目请求，并闪一次骨架屏——"快速切换"这件事本身就废了。这里把列表缓存在模块
// 作用域，换篇时直接复用，过期则后台刷新、前台继续显示旧列表。

import { effectScope, ref } from "vue";

import { usePosts } from "./usePosts";

const RAIL_PAGE_SIZE = 30;
// 软过期：过期后仍先展示旧列表，再后台换取新列表（stale-while-revalidate）。
const CACHE_TTL_MS = 5 * 60 * 1000;
// 「跟随当前文章」时，当前栏目至少还要有一篇别的文章才值得占一栏；
// 只剩当前这一篇就退化为全站最新，好过让人打开一个只有自己在里面的清单。
const MIN_SCOPE_POSTS = 2;

const railPosts = ref([]);
const railTotal = ref(0);
const railHasMore = ref(false);
const railLoadingMore = ref(false);
const railMode = ref("category");
const railCategory = ref("");
const railKey = ref("");
// 读者选定的清单范围："" = 跟随当前文章（本栏目），"latest" = 全站最新，其余为指定栏目。
// 它是「选择」而不是推断值，因此在换篇之间保持不变——读者选了算法，翻到工程篇时
// 左栏仍然停在算法，直到他自己改回来。
const railScope = ref("");

let store = null;
let committedScope = null;
let committedAt = 0;
let followCategory = "";
let token = 0;
let inflight = null;

function scopeKey(mode, category) {
  return mode === "latest" ? "latest" : `category:${category || ""}`;
}

function getStore() {
  if (store) return store;
  // usePosts 内部注册 onScopeDispose；模块作用域下没有活动的 effect scope，
  // 直接调用会打印 Vue 警告。用一个脱离的 scope 托管它，生命周期跟随页面。
  const owner = effectScope(true);
  store = owner.run(() => usePosts({ errorMessage: "文章清单加载失败。" }));
  return store;
}

function mirrorStore() {
  railPosts.value = store.posts.value;
  railTotal.value = store.total.value;
  railHasMore.value = store.hasMore.value;
  railLoadingMore.value = store.loadingMore.value;
}

function commit(mode, category) {
  mirrorStore();
  railMode.value = mode;
  railCategory.value = category;
  railKey.value = scopeKey(mode, category);
  committedScope = railScope.value;
  committedAt = Date.now();
}

/**
 * 只在这一步成功时提交列表：失败（或换篇导致 token 失效）时保留当前已渲染的内容，
 * 于是「过期后刷新」在读者眼里是一次静默替换，而不是闪一下骨架屏。
 */
async function loadList(params, { mode, category }, myToken) {
  const active = getStore();
  await active.loadPosts(params);
  if (myToken !== token || active.error.value) return null;
  commit(mode, category);
  return railPosts.value;
}

/** 加载「跟随当前文章」的范围：栏目过薄时退化为全站最新。 */
async function loadFollowScope(category) {
  const myToken = ++token;
  const active = getStore();

  await active.loadPosts({
    category: category || undefined,
    page: 1,
    limit: RAIL_PAGE_SIZE,
  });
  if (myToken !== token || active.error.value) return railPosts.value;

  if (!category || active.total.value < MIN_SCOPE_POSTS) {
    await active.loadPosts({ page: 1, limit: RAIL_PAGE_SIZE });
    if (myToken !== token || active.error.value) return railPosts.value;
    commit("latest", "");
    return railPosts.value;
  }

  commit("category", category);
  return railPosts.value;
}

/** 加载读者明确选定的范围：不做任何退化，选了就照办。 */
function loadExplicitScope(scope) {
  const myToken = ++token;
  if (scope === "latest") {
    return loadList({ page: 1, limit: RAIL_PAGE_SIZE }, { mode: "latest", category: "" }, myToken);
  }
  return loadList(
    { category: scope, page: 1, limit: RAIL_PAGE_SIZE },
    { mode: "category", category: scope },
    myToken,
  );
}

function loadSelectedScope() {
  return railScope.value === "" ? loadFollowScope(followCategory) : loadExplicitScope(railScope.value);
}

/**
 * 确保左侧清单与当前选择一致（未选择时跟随 `category` 栏目）。
 * 命中新鲜缓存时不会发请求，因此从清单点进下一篇不会产生任何列表请求。
 */
function ensureRail(category = "") {
  followCategory = category;
  const scope = railScope.value;
  const cacheKey = `${scope}|${category}`;

  if (committedScope === scope && railPosts.value.length) {
    if (Date.now() - committedAt < CACHE_TTL_MS) return Promise.resolve(railPosts.value);
    // 先记时间再刷新：刷新失败时也不该在读者每次换篇时重发同一个请求。
    committedAt = Date.now();
    return loadSelectedScope();
  }

  if (inflight?.key === cacheKey) return inflight.promise;

  const promise = loadSelectedScope()
    .finally(() => {
      if (inflight?.promise === promise) inflight = null;
    });
  inflight = { key: cacheKey, promise };
  return promise;
}

/** 读者在清单表头切换范围。传 "" 表示回到「跟随当前文章」。 */
function setRailScope(scope) {
  const next = typeof scope === "string" ? scope : "";
  if (next === railScope.value) return Promise.resolve(railPosts.value);
  railScope.value = next;
  return loadSelectedScope();
}

async function loadMoreRail() {
  if (!railHasMore.value || railLoadingMore.value) return railPosts.value;
  const active = getStore();
  const expectedKey = railKey.value;
  const expectedCount = railPosts.value.length;
  await active.loadMore();
  // 期间换篇了：列表已归新的 ensureRail 管，这里不要再镜像旧的加载结果。
  if (railKey.value !== expectedKey || railPosts.value.length !== expectedCount) {
    return railPosts.value;
  }
  mirrorStore();
  return railPosts.value;
}

export function usePostRail() {
  return {
    railPosts,
    railTotal,
    railHasMore,
    railLoadingMore,
    railMode,
    railCategory,
    railScope,
    ensureRail,
    setRailScope,
    loadMoreRail,
  };
}
