// 读迹数据层（DESIGN.md §6.3）：读完一篇，描一画；五篇成一个「正」。
//
// 数据只存本机：localStorage['zhizhi:read'] = { "<slug>": <读完时间戳 ms> }。
// 计数与有效 slug 取交集——已删除的文章不占画（目录由 /api/posts 拉一次，
// ≤ 50 篇足够覆盖；超过后仅影响交集精度，读迹封顶也只画 12 组）。
// localStorage 不可用时：readable = false，读迹区与已读标记整体不渲染，且不报错。

import { computed, ref } from "vue";

import { getPosts } from "../services/api";

const STORAGE_KEY = "zhizhi:read";

function probeStorage() {
  try {
    localStorage.setItem("zhizhi:probe", "1");
    localStorage.removeItem("zhizhi:probe");
    return true;
  } catch {
    return false;
  }
}

const readable = probeStorage();

function loadLog() {
  if (!readable) return {};
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    return raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  } catch {
    return {};
  }
}

const readLog = ref(loadLog());

// 有效文章目录（模块级单例请求，全站只拉一次）
const catalogSlugs = ref([]);
const catalogTotal = ref(0);
const catalogReady = ref(false);
let catalogRequest = null;

async function ensureCatalog() {
  if (catalogRequest) return catalogRequest;
  catalogRequest = getPosts({ limit: 50 })
    .then((list) => {
      catalogSlugs.value = (list?.items || []).map((item) => item.slug).filter(Boolean);
      catalogTotal.value = Number.isFinite(list?.total) ? list.total : catalogSlugs.value.length;
      catalogReady.value = true;
    })
    .catch(() => {
      // 目录拉不到时计数退回本地事实（不交集），下次挂载再试
      catalogRequest = null;
    });
  return catalogRequest;
}

function saveLog() {
  if (!readable) return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(readLog.value));
  } catch {
    /* 存不进去就只保留内存态 */
  }
}

export function useReadLog() {
  const readCount = computed(() => {
    const slugs = Object.keys(readLog.value);
    if (!catalogReady.value) return slugs.length;
    const valid = new Set(catalogSlugs.value);
    return slugs.filter((slug) => valid.has(slug)).length;
  });

  const totalCount = computed(() => catalogTotal.value);

  function isRead(slug) {
    return Boolean(slug && readLog.value[slug]);
  }

  /** 读完一篇：未记录时落笔（返回 true 表示这是新的一画）。 */
  function markRead(slug) {
    if (!readable || !slug || readLog.value[slug]) return false;
    readLog.value = { ...readLog.value, [slug]: Date.now() };
    saveLog();
    return true;
  }

  /** 一键清空（页脚「清除读迹」）。 */
  function clearRead() {
    readLog.value = {};
    saveLog();
  }

  return {
    readable,
    readLog,
    readCount,
    totalCount,
    catalogReady,
    ensureCatalog,
    isRead,
    markRead,
    clearRead,
  };
}
