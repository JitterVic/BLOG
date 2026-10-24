// 左栏文章态的共享状态（模块级单例）。
//
// 左栏随页面切换内容（DESIGN.md §4.2）：列表页里它是栏目索引，文章页里它是本文目录。
// 目录数据由 PostView 构建后写入这里，AppRail / TopBar 读取渲染；
// 文章页卸载时 PostView 调 resetRailState()，左栏随之回到栏目索引。

import { ref } from "vue";

const articleToc = ref([]); // [{ id, label, level }]
const articleActiveId = ref("");
const articleProgress = ref(0); // 0 ~ 1
const articleCategory = ref("");

export function useRailState() {
  function setArticle({ toc = [], category = "" } = {}) {
    articleToc.value = toc;
    articleCategory.value = category;
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
  }

  return {
    articleToc,
    articleActiveId,
    articleProgress,
    articleCategory,
    setArticle,
    setActiveHeading,
    setProgress,
    resetRailState,
  };
}
