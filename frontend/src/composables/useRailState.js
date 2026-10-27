// 左栏文章态的共享状态（模块级单例）。
//
// 左栏随页面切换内容（DESIGN.md §4.2）：列表页里它是栏目索引，文章页里它是
// 栏目文章目录（本栏目各篇，当前篇高亮）；本文目录自 v2.2 起改挂文章页右栏批注栏，
// 仍由 PostView 写入这里供 TopBar 窄屏进度线与右栏自身读取。
// 文章页卸载时 PostView 调 resetRailState()，左栏随之回到栏目索引。

import { ref } from "vue";

const articleToc = ref([]); // [{ id, label, level }]
const articleActiveId = ref("");
const articleProgress = ref(0); // 0 ~ 1
const articleCategory = ref("");
const articleSiblings = ref([]); // [{ slug, title }] 当前栏目下的文章目录

export function useRailState() {
  function setArticle({ toc = [], category = "", siblings = [] } = {}) {
    articleToc.value = toc;
    articleCategory.value = category;
    articleSiblings.value = siblings;
    articleActiveId.value = toc[0]?.id || "";
    articleProgress.value = 0;
  }

  function setActiveHeading(id) {
    articleActiveId.value = id;
  }

  function setProgress(value) {
    articleProgress.value = Math.min(1, Math.max(0, value));
  }

  function resetRailState() {
    articleToc.value = [];
    articleActiveId.value = "";
    articleProgress.value = 0;
    articleCategory.value = "";
    articleSiblings.value = [];
  }

  return {
    articleToc,
    articleActiveId,
    articleProgress,
    articleCategory,
    articleSiblings,
    setArticle,
    setActiveHeading,
    setProgress,
    resetRailState,
  };
}
