<script setup>
import { computed, onMounted, watch } from "vue";
import { useRoute } from "vue-router";

import CursorEffects from "./components/CursorEffects.vue";
import FloatingCat from "./components/FloatingCat.vue";
import SiteHeader from "./components/SiteHeader.vue";
import { usePageMeta } from "./composables/usePageMeta";
import { useReveal } from "./composables/useReveal";
import { useSite } from "./composables/useSite";

const route = useRoute();
const { site, ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: true });
const currentYear = new Date().getFullYear();

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

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // The child views handle their own fallback UI.
  }
  refreshReveal();
});
</script>

<template>
  <div class="page-shell print-shell" :class="pageTheme">
    <CursorEffects />
    <FloatingCat />
    <SiteHeader />

    <main class="app-main print-main">
      <router-view v-slot="{ Component, route: viewRoute }">
        <Transition name="page-fade" mode="out-in" @after-enter="refreshReveal">
          <component :is="Component" :key="viewRoute.fullPath" />
        </Transition>
      </router-view>
    </main>

    <footer class="site-footer print-colophon">
      <div class="colophon-grid">
        <div class="colophon-brand">
          <div class="colophon__mark">{{ site?.name || "至知" }}.</div>
          <div class="colophon__issn">DIGITAL JOURNAL · {{ currentYear }}</div>
          <p class="colophon__headline">{{ site?.headline || "记录成长的点点滴滴" }}</p>
        </div>

        <div class="colophon-block colophon-quote">
          <h4>Motto</h4>
          <p class="colophon-quote__text">功不唐捐，玉汝于成。愿每一次记录都成为向上的台阶，时间会把这些点滴装订成属于你的答案。</p>
        </div>
      </div>

      <div class="colophon__legal">
        <span>© {{ currentYear }} {{ site?.name || "至知" }}</span>
        <span class="colophon__legal-sep" aria-hidden="true">·</span>
        <span>日拱一卒</span>
      </div>
    </footer>
  </div>
</template>
