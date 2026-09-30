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
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: true });

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
    <InitialLoader />
    <RouteProgress />
    <CursorEffects />
    <CatPet />
    <SiteHeader />

    <main class="app-main print-main">
      <router-view v-slot="{ Component, route: viewRoute }">
        <Transition name="page-fade" mode="out-in" @after-enter="refreshReveal">
          <component :is="Component" :key="viewRoute.fullPath" />
        </Transition>
      </router-view>
    </main>

    <!-- 首页采用三页整屏翻页布局，不保留页脚版权栏 -->
    <SiteFooter v-if="route.name !== 'home'" />
  </div>
</template>
