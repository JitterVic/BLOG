// 标题共享转场（DESIGN.md §7）：点击列表行 / 封面 / 首页近笺 / 文末相邻文章进入详情时，
// 被点击的标题与详情 h1 共用 view-transition-name: post-title。
// 「同一时刻只设在一个元素上」：详情 h1 常驻该 name（prose.css），
// 出发侧标题只在转场期间临时持有（直接取 event.currentTarget，v-for 行各自独立）。
// 文末「上一篇 / 下一篇」点击时，当前页 h1 正持有同名——先摘除再给出发元素，
// 否则同屏两个同名元素会让 View Transition 报错失效。
// VT 激活期间在 <html> 挂 data-vt-active，App.vue 的路由微淡入据此禁用，避免双重动画。
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

    // 出发前清除页面上已有的常驻同名元素（文章页 h1），防止同名冲突
    const existingHeading = document.querySelector(".article-head__title");
    if (existingHeading && existingHeading !== el) {
      existingHeading.style.viewTransitionName = "none";
    }

    const root = document.documentElement;
    el.style.viewTransitionName = "post-title";
    const transition = document.startViewTransition(async () => {
      root.dataset.vtActive = "true";
      el.style.viewTransitionName = "";
      await router.push(to);
      await nextTick();
    });
    transition.finished.finally(() => {
      delete root.dataset.vtActive;
      el.style.viewTransitionName = "";
      if (existingHeading && existingHeading !== el) {
        existingHeading.style.viewTransitionName = "";
      }
    });
  }

  return { handleOpen };
}
