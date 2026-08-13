// 文章目录：从正文收集 h2/h3 章节、跟随阅读位置高亮当前章节。

import { nextTick, onScopeDispose, ref } from "vue";

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function getReadingLine() {
  const header = document.querySelector(".site-header");
  const headerBottom = header?.getBoundingClientRect().bottom || 0;
  let readingLine = Math.max(96, headerBottom + 48);

  if (window.matchMedia?.("(max-width: 1280px)").matches) {
    const toc = document.querySelector(".article-toc");
    if (toc) {
      const tocRect = toc.getBoundingClientRect();
      const tocTop = Number.parseFloat(window.getComputedStyle(toc).top) || 0;
      const tocIsStuck = tocRect.top <= tocTop + 2 && tocRect.bottom > tocTop;
      if (tocIsStuck) readingLine = Math.max(readingLine, tocRect.bottom + 20);
    }
  }

  return Math.min(readingLine, Math.max(window.innerHeight - 48, 80));
}

export function useTableOfContents(bodyRef) {
  const tableOfContents = ref([]);
  const activeHeading = ref("");
  const cleanupHandlers = [];
  let headings = [];
  let trackingFrame = 0;
  let isTracking = false;

  function runCleanups() {
    while (cleanupHandlers.length) {
      const cleanup = cleanupHandlers.pop();
      cleanup?.();
    }
  }

  function updateActiveHeading() {
    trackingFrame = 0;
    if (!headings.length) return;

    const documentElement = document.documentElement;
    const documentHeight = Math.max(documentElement.scrollHeight, document.body.scrollHeight);
    const reachedDocumentEnd = window.scrollY + window.innerHeight >= documentHeight - 2;

    if (reachedDocumentEnd) {
      activeHeading.value = headings.at(-1).id;
      return;
    }

    const readingLine = getReadingLine();
    let currentHeading = headings[0];

    for (const heading of headings) {
      if (heading.getBoundingClientRect().top > readingLine) break;
      currentHeading = heading;
    }

    activeHeading.value = currentHeading.id;
  }

  function scheduleActiveUpdate() {
    if (trackingFrame) return;
    trackingFrame = window.requestAnimationFrame(updateActiveHeading);
  }

  function startTracking() {
    if (isTracking) return;
    isTracking = true;
    window.addEventListener("scroll", scheduleActiveUpdate, { passive: true });
    window.addEventListener("resize", scheduleActiveUpdate, { passive: true });
    scheduleActiveUpdate();
  }

  function stopTracking() {
    if (isTracking) {
      window.removeEventListener("scroll", scheduleActiveUpdate);
      window.removeEventListener("resize", scheduleActiveUpdate);
      isTracking = false;
    }
    if (trackingFrame) {
      window.cancelAnimationFrame(trackingFrame);
      trackingFrame = 0;
    }
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
    startTracking();
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
