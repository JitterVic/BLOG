<script setup>
// 顶栏（DESIGN.md §4.3，< 1100px）：左栏隐去时接管「我在哪」。
// 「菜单」打开原生 <dialog>（showModal），内容与左栏相同：导航 / 栏目 / 搜索 / 读迹 / 主题。
// 文章页：顶栏底部有 2px 阅读进度线（--indigo，scaleX）。

import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";

import RailSearch from "./RailSearch.vue";
import ReadTrace from "./ReadTrace.vue";
import { useRailState } from "../composables/useRailState";
import { useSite } from "../composables/useSite";
import { useTheme } from "../composables/useTheme";

const route = useRoute();
const { site } = useSite();
const { articleProgress } = useRailState();
const { label: themeLabel, cycle: cycleTheme } = useTheme();

const menuRef = ref(null);
const searchInputRef = ref(null);

const isPost = computed(() => route.name === "post");

const NAV_ITEMS = [
  { name: "home", label: "首页", to: "/" },
  { name: "posts", label: "文章", to: "/posts" },
  { name: "about", label: "关于", to: "/about" },
];

const categories = computed(() => {
  const raw = site.value?.categories || [];
  return raw
    .map((item) =>
      typeof item === "string"
        ? { name: item, total: 0 }
        : {
            name: item?.name || "",
            total: Number(item?.total ?? item?.count) || 0,
          },
    )
    .filter((item) => item.name);
});

function isNavActive(name) {
  if (name === "home") return route.name === "home";
  return route.name === name || (name === "posts" && route.name === "post");
}

function isCategoryActive(name) {
  return route.name === "posts" && route.query.cat === name;
}

function openMenu({ focusSearch = false } = {}) {
  const dialog = menuRef.value;
  if (!dialog) return;
  if (!dialog.open) dialog.showModal();
  if (focusSearch) {
    window.setTimeout(() => {
      searchInputRef.value?.focus?.();
    }, 0);
  }
}

function closeMenu() {
  menuRef.value?.close?.();
}

// 菜单里的链接导航后自动收起菜单
watch(
  () => route.fullPath,
  () => closeMenu(),
);

// 窄屏下 `/` 快捷键（App.vue 派发）：左栏不在场，打开菜单并聚焦搜索框
function handleOpenSearch() {
  openMenu({ focusSearch: true });
}

onMounted(() => window.addEventListener("zhizhi:open-search", handleOpenSearch));
onBeforeUnmount(() => {
  window.removeEventListener("zhizhi:open-search", handleOpenSearch);
  closeMenu();
});
</script>

<template>
  <header class="topbar">
    <RouterLink class="topbar__brand" to="/">至知</RouterLink>

    <div class="topbar__actions">
      <button type="button" class="topbar__icon-btn" aria-label="搜索文章" @click="openMenu({ focusSearch: true })">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2" />
          <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
      </button>
      <button type="button" class="topbar__icon-btn" aria-label="打开菜单" @click="openMenu()">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <line x1="4" y1="7" x2="20" y2="7" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          <line x1="4" y1="12" x2="20" y2="12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          <line x1="4" y1="17" x2="20" y2="17" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
        </svg>
      </button>
    </div>

    <!-- 文章页阅读进度线（§4.3） -->
    <div
      v-if="isPost"
      class="topbar__progress"
      :style="{ transform: `scaleX(${articleProgress})` }"
      aria-hidden="true"
    ></div>

    <dialog ref="menuRef" class="topbar-menu" aria-label="站点菜单" @click.self="closeMenu">
      <div class="topbar-menu__body">
        <div class="topbar-menu__head">
          <span class="topbar-menu__title">至知</span>
          <button type="button" class="text-btn" @click="closeMenu">关闭</button>
        </div>

        <nav class="topbar-menu__nav" aria-label="站点导航">
          <RouterLink
            v-for="item in NAV_ITEMS"
            :key="item.name"
            class="topbar-menu__link"
            :to="item.to"
            :aria-current="isNavActive(item.name) ? 'page' : undefined"
          >
            <span class="marker-sweep" :class="{ 'is-on': isNavActive(item.name) }">{{ item.label }}</span>
          </RouterLink>
        </nav>

        <div class="topbar-menu__section">
          <p class="rail-mid__label">栏目</p>
          <nav class="topbar-menu__cats" aria-label="栏目">
            <RouterLink
              class="topbar-menu__link"
              :to="{ name: 'posts' }"
              :aria-current="route.name === 'posts' && !route.query.cat ? 'page' : undefined"
            >
              <span class="marker-sweep" :class="{ 'is-on': route.name === 'posts' && !route.query.cat }">全部</span>
            </RouterLink>
            <RouterLink
              v-for="category in categories"
              :key="category.name"
              class="topbar-menu__link"
              :to="{ name: 'posts', query: { cat: category.name } }"
              :aria-current="isCategoryActive(category.name) ? 'page' : undefined"
            >
              <span class="marker-sweep" :class="{ 'is-on': isCategoryActive(category.name) }">{{ category.name }}</span>
            </RouterLink>
          </nav>
        </div>

        <div class="topbar-menu__section">
          <RailSearch ref="searchInputRef" />
        </div>

        <div class="topbar-menu__section topbar-menu__foot">
          <ReadTrace />
          <p class="rail-theme">
            <span class="rail-foot__label">主题</span>
            <button type="button" class="rail-theme__btn" @click="cycleTheme">{{ themeLabel }}</button>
          </p>
        </div>
      </div>
    </dialog>
  </header>
</template>
