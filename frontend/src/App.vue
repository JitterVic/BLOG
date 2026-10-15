<script setup>
import { computed, onBeforeUnmount, onMounted, watch } from "vue";
import { useRoute } from "vue-router";

import CatPet from "./components/pet/CatPet.vue";
import CursorEffects from "./components/CursorEffects.vue";
import InitialLoader from "./components/InitialLoader.vue";
import RouteProgress from "./components/RouteProgress.vue";
import SiteFooter from "./components/SiteFooter.vue";
import SiteHeader from "./components/SiteHeader.vue";
import { usePageFlip } from "./composables/usePageFlip";
import { usePageMeta } from "./composables/usePageMeta";
import { useReveal } from "./composables/useReveal";
import { useSite } from "./composables/useSite";

const route = useRoute();

const { site, ensureSite } = useSite();
const { refresh: refreshReveal, replayReveal } = useReveal({ reobserveOnRoute: true });

/**
 * 页面切换后重播入场动效。
 *
 * 路由视图用 `:key="viewRoute.path"` 强制重建（只按 path，不按 fullPath）：
 * 筛选、翻页这类只改查询串的导航必须留在同一个视图实例里就地更新——`PostsView`
 * 为此专门监听了 `route.query`。若把 fullPath 挂上 key，`加载更多` 把 page 写回
 * URL 的那一刻就会整页重建：先是骨架屏（看起来像刷新了页面），随后 onMounted 再
 * 从头拉一遍列表，才补出第二页的内容。
 *
 * 重建后的元素初始就落在视口内时，观察器回调与 Vue 补丁存在竞态，会出现「切回来
 * 是静止的」。这里在过渡结束（页面已就位）后显式重播一次，保证每次切页都能看到
 * 入场层次。
 */
function replayPageReveal() {
  const view = document.querySelector(".print-main > .print-page, .print-main > .home-view, .print-main > .print-subpage, .print-main > .print-post-view");
  // 路由切换后视图是新建的，观察器通常已经把入场启动了（新元素一挂载就落在
  // 视口内）；此时再重播会换掉逐字浮现的动画名，把标题从半途重启 —— 表现为
  // 「从文章页/关于页切回封面页时标题渲染了两遍」。所以这一入口跳过已在播的
  // 逐字动画，只把容器（含未揭示元素）标成已揭示。
  replayReveal(view || document.querySelector(".print-main"), { skipRunningCharAnimation: true });
}

// 加载页离场后立刻重播一次：首屏的入场动效必须在这一刻才可见
// （加载页整屏遮挡约 1.55s，封面若在被遮挡期间就入场，揭开时已是静止的）。
function onLoaderReady() {
  // 摘掉「加载页遮挡中」的挂起状态：`html.loader-done` 一旦加上，
  // 下面那条 `html:not(.loader-done)` 的按住规则立即失效，
  // 封面的 `.rv` 与逐字浮现单字才回到可过渡的基准态，紧接着重播即可见。
  document.documentElement.classList.add("loader-done");
  requestAnimationFrame(() => replayPageReveal());
}

const pageTheme = computed(() => {
  const name = route.name;
  if (name === "home") return "page-theme-home";
  if (name === "posts" || name === "post") return "page-theme-articles";
  if (name === "about") return "page-theme-about";
  return "page-theme-default";
});

usePageMeta(() => {
  const name = route.name;
  const siteName = site.value?.name || "至知";
  if (name === "posts") return { title: `文章目录 · ${siteName}`, description: "浏览至知的技术实践、项目复盘、阅读笔记与长期学习记录。" };
  if (name === "about") return { title: `关于 · ${siteName}`, description: site.value?.summary || "了解这份个人技术博客的作者、写作方向与联系方式。" };
  if (name === "post") return { title: `文章 · ${siteName}`, description: "正在打开文章……" };
  if (name === "not-found") return { title: `页面未收录 · ${siteName}`, description: "你访问的页面不存在，返回文章目录继续阅读。" };
  return { title: `${siteName} · Journal`, description: site.value?.summary || "记录技术实践、项目复盘和长期学习的个人博客。" };
});

// 首页三版整屏翻页：滚轮/键盘由 usePageFlip 接管（向下翻下一版、向上翻上一版），
// 同时仅在首页给根元素挂 home-paging 类，驱动 pages.css 中的整屏布局与进度隐藏。
usePageFlip();

watch(
  () => route.name,
  (name) => {
    document.documentElement.classList.toggle("home-paging", name === "home");
  },
  { immediate: true },
);

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // The child views handle their own fallback UI.
  }
  refreshReveal();
});

onBeforeUnmount(() => {
  document.documentElement.classList.remove("home-paging");
});
</script>

<template>
  <div class="page-shell print-shell" :class="pageTheme">
    <InitialLoader @ready="onLoaderReady" />
    <RouteProgress />
    <CursorEffects />
    <CatPet />
    <SiteHeader />

    <main class="app-main print-main">
      <router-view v-slot="{ Component, route: viewRoute }">
        <Transition name="page-fade" mode="out-in" @after-enter="replayPageReveal">
          <component :is="Component" :key="viewRoute.path" />
        </Transition>
      </router-view>
    </main>

    <!-- 首页采用三页整屏翻页布局，不保留页脚版权栏 -->
    <SiteFooter v-if="route.name !== 'home'" />
  </div>
</template>
