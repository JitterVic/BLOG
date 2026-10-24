// 文章目录：从正文收集 h2/h3 章节、跟随阅读位置高亮当前章节（DESIGN.md §4.2）。
//
// 当前项由 IntersectionObserver 判定（rootMargin: -20% 0px -70% 0px，
// 即视口中部的「阅读带」）；可见集合里最靠后的标题为当前项，全部不可见时保持
// 上一个（快速滚动时不闪烁）。观察器随文章页卸载 disconnect()。

import { nextTick, onScopeDispose, ref } from "vue";

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

export function useTableOfContents(bodyRef) {
  const tableOfContents = ref([]);
  const activeHeading = ref("");
  const cleanupHandlers = [];
  let observer = null;
  let headings = [];

  function runCleanups() {
    while (cleanupHandlers.length) {
      const cleanup = cleanupHandlers.pop();
      cleanup?.();
    }
  }

  function stopTracking() {
    observer?.disconnect();
    observer = null;
    headings = [];
  }

  /**
   * 重新扫描正文标题。enhance(body, headings) 在目录构建后调用，
   * 可返回一个 cleanup 函数，会在下次构建或组件销毁时执行。
   */
  async function buildNavigation(enhance) {
    stopTracking();
    runCleanups();
    tableOfContents.value = [];
    activeHeading.value = "";
    await nextTick();

    const body = bodyRef.value;
    if (!body) return;

    headings = Array.from(body.querySelectorAll("h2, h3"));
    tableOfContents.value = headings.map((heading, index) => {
      if (!heading.id) heading.id = `article-section-${index + 1}`;
      return {
        id: heading.id,
        label: heading.textContent?.trim() || `章节 ${index + 1}`,
        level: heading.tagName === "H3" ? 3 : 2,
      };
    });

    const cleanup = typeof enhance === "function" ? enhance(body, headings) : null;
    if (typeof cleanup === "function") {
      cleanupHandlers.push(cleanup);
    }

    if (!tableOfContents.value.length) {
      headings = [];
      return;
    }

    activeHeading.value = tableOfContents.value[0].id;

    const visible = new Map();
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          visible.set(entry.target, entry.isIntersecting);
        }
        const current = headings.filter((heading) => visible.get(heading)).at(-1);
        if (current) activeHeading.value = current.id;
      },
      { rootMargin: "-20% 0px -70% 0px", threshold: 0 },
    );
    headings.forEach((heading) => observer.observe(heading));
  }

  function reset() {
    stopTracking();
    runCleanups();
    tableOfContents.value = [];
    activeHeading.value = "";
  }

  function scrollToHeading(id) {
    const heading = document.getElementById(id);
    if (!heading) return;
    activeHeading.value = id;
    heading.scrollIntoView({
      behavior: prefersReducedMotion() ? "auto" : "smooth",
      block: "start",
    });
  }

  onScopeDispose(() => {
    reset();
  });

  return {
    tableOfContents,
    activeHeading,
    buildNavigation,
    reset,
    scrollToHeading,
  };
}
