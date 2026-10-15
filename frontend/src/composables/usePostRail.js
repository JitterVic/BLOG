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
// 当前篇之外至少还要有两篇可切换，清单才值得占一栏。
const MIN_SCOPE_POSTS = 3;

const railPosts = ref([]);
const railTotal = ref(0);
const railHasMore = ref(false);
const railLoadingMore = ref(false);
const railMode = ref("category");
const railCategory = ref("");
const railKey = ref("");

let store = null;
let committedKey = "";
let committedAt = 0;
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
  committedKey = railKey.value;
  committedAt = Date.now();
}

/**
 * 只在这一步成功时提交列表：失败（或换篇导致 token 失效）时保留当前已渲染的内容，
 * 于是「过期后刷新」在读者眼里是一次静默替换，而不是闪一下骨架屏。
 */
async function loadScope(category) {
  const active = getStore();
  const myToken = ++token;

  await active.loadPosts({ category: category || undefined, page: 1, limit: RAIL_PAGE_SIZE });
  if (myToken !== token || active.error.value) return railPosts.value;

  let mode = "category";
  let effectiveCategory = category || "";

  if (active.total.value < MIN_SCOPE_POSTS) {
    await active.loadPosts({ page: 1, limit: RAIL_PAGE_SIZE });
    if (myToken !== token || active.error.value) return railPosts.value;
    mode = "latest";
    effectiveCategory = "";
  }

  commit(mode, effectiveCategory);
  return railPosts.value;
}

/**
 * 确保左侧清单为 `category` 栏目（栏目过薄时退化为全站最新）。
 * 命中新鲜缓存时不会发请求，因此从清单点进下一篇不会产生任何列表请求。
 */
function ensureRail(category = "") {
  const categoryKey = scopeKey("category", category);

  if (categoryKey === committedKey && railPosts.value.length) {
    if (Date.now() - committedAt < CACHE_TTL_MS) return Promise.resolve(railPosts.value);
    // 先记时间再刷新：刷新失败时也不该在读者每次换篇时重发同一个请求。
    committedAt = Date.now();
    return loadScope(category);
  }

  if (inflight?.key === categoryKey) return inflight.promise;

  const promise = loadScope(category)
    .finally(() => {
      if (inflight?.promise === promise) inflight = null;
    });
  inflight = { key: categoryKey, promise };
  return promise;
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
    ensureRail,
    loadMoreRail,
  };
}
