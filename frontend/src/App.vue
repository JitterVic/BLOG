<script setup>
// 应用壳（DESIGN.md §4）：≥1100px 左栏常驻；<1100px 顶栏接管。
// 页面正常滚动，不劫持任何输入；动效只剩 §7 表中四件。

import { nextTick, onBeforeUnmount, onMounted, watch } from "vue";
import { useRoute } from "vue-router";

import AppRail from "./components/AppRail.vue";
import CatPet from "./components/pet/CatPet.vue";
import SiteFooter from "./components/SiteFooter.vue";
import TopBar from "./components/TopBar.vue";
import { usePageMeta } from "./composables/usePageMeta";
import { useSite } from "./composables/useSite";

const route = useRoute();
const { site, ensureSite } = useSite();

usePageMeta(() => {
  const name = route.name;
  const siteName = site.value?.name || "至知";
  if (name === "posts") return { title: `文章 · ${siteName}`, description: "浏览至知的技术实践、项目复盘、阅读笔记与长期学习记录。" };
  if (name === "about") return { title: `关于 · ${siteName}`, description: site.value?.summary || "了解这份个人博客的作者、写作方向与联系方式。" };
  if (name === "post") return { title: `文章 · ${siteName}`, description: "正在打开文章……" };
  if (name === "not-found") return { title: `找不到这一页 · ${siteName}`, description: "你访问的页面不存在，回到首页或全部文章继续阅读。" };
  return { title: siteName, description: site.value?.summary || "至知：记录技术实践、项目复盘和长期学习的个人博客。" };
});

/** `/` 聚焦搜索（§6.6）：焦点已在输入控件内时不抢。窄屏左栏不在场，交给顶栏菜单。 */
function isTypingTarget(target) {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable
    || target.closest("input, textarea, select, dialog[open]");
}

function handleSlashKey(event) {
  if (event.key !== "/" || event.ctrlKey || event.metaKey || event.altKey) return;
  if (isTypingTarget(event.target)) return;
  event.preventDefault();
  const input = document.querySelector(".rail .rail-search__input");
  if (input && input.offsetParent) {
    input.focus();
  } else {
    window.dispatchEvent(new CustomEvent("zhizhi:open-search"));
  }
}

/**
 * SPA 换页后的焦点移交：客户端路由不重置焦点，键盘用户每翻一页都会重走一遍导航。
 * 只认 path 不认 query —— 筛选/翻页是同一视图内的就地更新，抢焦点会打断输入。
 */
let focusRouteSettled = false;
watch(
  () => route.path,
  async () => {
    if (!focusRouteSettled) {
      focusRouteSettled = true;
      return;
    }
    await nextTick();
    const main = document.getElementById("main-content");
    if (main && !main.contains(document.activeElement)) {
      main.focus({ preventScroll: true });
    }
  },
);

onMounted(() => {
  document.addEventListener("keydown", handleSlashKey);
  ensureSite().catch(() => {
    // 各视图有自己的兜底 UI，站点元信息缺失不阻塞版面。
  });
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleSlashKey);
});
</script>

<template>
  <div class="shell">
    <a class="skip-link" href="#main-content">跳到正文</a>
    <AppRail />
    <div class="shell-main">
      <TopBar />
      <main id="main-content" class="app-main" tabindex="-1">
        <router-view />
      </main>
      <SiteFooter />
    </div>
  </div>
  <CatPet />
</template>
