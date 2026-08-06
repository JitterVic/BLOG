// 阅读进度：跟随滚动计算文章正文的阅读完成度（0~1）。

import { onBeforeUnmount, onMounted, ref } from "vue";

export function useReadingProgress(bodyRef) {
  const readingProgress = ref(0);
  let progressFrame = null;

  function update() {
    if (progressFrame) return;
    progressFrame = window.requestAnimationFrame(() => {
      progressFrame = null;
      const body = bodyRef.value;
      if (!body) {
        readingProgress.value = 0;
        return;
      }
      const bodyTop = body.getBoundingClientRect().top + window.scrollY;
      const readableHeight = Math.max(body.offsetHeight - window.innerHeight, 1);
      const current = window.scrollY - bodyTop;
      readingProgress.value = Math.min(1, Math.max(0, current / readableHeight));
    });
  }

  onMounted(() => {
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("scroll", update);
    window.removeEventListener("resize", update);
    if (progressFrame) window.cancelAnimationFrame(progressFrame);
  });

  return { readingProgress, update };
}
