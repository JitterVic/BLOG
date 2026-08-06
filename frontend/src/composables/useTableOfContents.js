// 文章目录：从正文收集 h2/h3 章节、跟随滚动高亮当前章节。

import { nextTick, onScopeDispose, ref } from "vue";

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

export function useTableOfContents(bodyRef) {
  const tableOfContents = ref([]);
  const activeHeading = ref("");
  let headingObserver = null;
  const cleanupHandlers = [];

  function runCleanups() {
    while (cleanupHandlers.length) {
      const cleanup = cleanupHandlers.pop();
      cleanup?.();
    }
  }

  function disconnectObserver() {
    headingObserver?.disconnect();
    headingObserver = null;
  }

  /**
   * 重新扫描正文标题。enhance(body, headings) 在目录构建后调用，
   * 可返回一个 cleanup 函数，会在下次构建或组件销毁时执行。
   */
  async function buildNavigation(enhance) {
    disconnectObserver();
    runCleanups();
    tableOfContents.value = [];
    activeHeading.value = "";
    await nextTick();

    const body = bodyRef.value;
    if (!body) return;

    const headings = Array.from(body.querySelectorAll("h2, h3"));
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

    if (!tableOfContents.value.length) return;
    activeHeading.value = tableOfContents.value[0].id;

    if (!("IntersectionObserver" in window)) return;
    headingObserver = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) activeHeading.value = visible[0].target.id;
      },
      { rootMargin: "-18% 0px -68% 0px", threshold: [0, 1] },
    );
    headings.forEach((heading) => headingObserver.observe(heading));
  }

  function reset() {
    disconnectObserver();
    runCleanups();
    tableOfContents.value = [];
    activeHeading.value = "";
  }

  function scrollToHeading(id) {
    const heading = document.getElementById(id);
    if (!heading) return;
    heading.scrollIntoView({
      behavior: prefersReducedMotion() ? "auto" : "smooth",
      block: "start",
    });
    activeHeading.value = id;
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
