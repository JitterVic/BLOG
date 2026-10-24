// 标题共享转场（DESIGN.md §7）：点击列表行 / 封面进入文章时，
// 被点击的标题与文章 h1 共用 view-transition-name: post-title。
// 「同一时刻只设在一个元素上」：文章 h1 常驻该 name（prose.css），
// 出发侧标题只在转场期间临时持有（直接取 event.currentTarget，v-for 行各自独立）。
// 渐进增强：不支持或已请求减弱动效时走默认导航。

import { nextTick } from "vue";
import { useRouter } from "vue-router";

export function useTitleMorph() {
  const router = useRouter();

  function prefersReducedMotion() {
    return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
  }

  function handleOpen(event, to) {
    if (
      event.defaultPrevented
      || event.button !== 0
      || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey
    ) return;
    if (typeof document.startViewTransition !== "function") return;
    if (prefersReducedMotion()) return;

    event.preventDefault();
    const el = event.currentTarget;
    if (!el || !el.style) {
      router.push(to);
      return;
    }
    el.style.viewTransitionName = "post-title";
    const transition = document.startViewTransition(async () => {
      el.style.viewTransitionName = "";
      await router.push(to);
      await nextTick();
    });
    transition.finished.finally(() => {
      el.style.viewTransitionName = "";
    });
  }

  return { handleOpen };
}
