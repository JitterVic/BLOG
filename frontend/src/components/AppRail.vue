<script setup>
// 左栏（DESIGN.md §4.2，≥ 1100px）：回答「我在哪」「附近有什么」。
// 列表页里它是栏目索引；文章页里它是本文目录 + 阅读进度（数据经 useRailState 共享）。

import { computed } from "vue";
import { useRoute } from "vue-router";
import { RouterLink } from "vue-router";

import RailSearch from "./RailSearch.vue";
import ReadTrace from "./ReadTrace.vue";
import { useRailState } from "../composables/useRailState";
import { useSite } from "../composables/useSite";
import { useTheme } from "../composables/useTheme";

const route = useRoute();
const { site } = useSite();
const { articleToc, articleActiveId, articleProgress, articleCategory } = useRailState();
const { label: themeLabel, cycle: cycleTheme } = useTheme();

const isPost = computed(() => route.name === "post");

const NAV_ITEMS = [
  { name: "home", label: "首页", to: "/" },
  { name: "posts", label: "文章", to: "/posts" },
  { name: "about", label: "关于", to: "/about" },
];

const backToCategory = computed(() => ({
  label: articleCategory.value ? `回到「${articleCategory.value}」` : "回到文章列表",
  to: articleCategory.value
    ? { name: "posts", query: { cat: articleCategory.value } }
    : { name: "posts" },
}));

// site.categories: [{ name, total }]（服务端按篇数统计），兼容历史字符串形状
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

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function jumpToHeading(id) {
  const heading = document.getElementById(id);
  if (!heading) return;
  heading.scrollIntoView({
    behavior: prefersReducedMotion() ? "auto" : "smooth",
    block: "start",
  });
}

const progressPercent = computed(() => Math.round(articleProgress.value * 100));
</script>

<template>
  <aside class="rail">
    <p class="rail-brand"><RouterLink class="rail-brand__link" to="/">至知</RouterLink></p>

    <nav class="rail-nav" aria-label="站点导航">
      <template v-if="!isPost">
        <RouterLink
          v-for="item in NAV_ITEMS"
          :key="item.name"
          class="rail-nav__link"
          :to="item.to"
          :aria-current="isNavActive(item.name) ? 'page' : undefined"
        >
          <span class="marker-sweep" :class="{ 'is-on': isNavActive(item.name) }">{{ item.label }}</span>
        </RouterLink>
      </template>
      <RouterLink v-else class="rail-nav__link" :to="backToCategory.to">
        {{ backToCategory.label }}
      </RouterLink>
    </nav>

    <div class="rail-mid">
      <template v-if="isPost && articleToc.length">
        <p class="rail-mid__label">本文目录</p>
        <nav class="rail-toc" aria-label="本文目录">
          <a
            v-for="item in articleToc"
            :key="item.id"
            class="rail-toc__link"
            :class="{ 'rail-toc__link--sub': item.level === 3 }"
            :href="`#${item.id}`"
            :aria-current="item.id === articleActiveId ? 'location' : undefined"
            @click.prevent="jumpToHeading(item.id)"
          >
            <span
              class="marker-sweep"
              :class="{ 'is-on': item.id === articleActiveId }"
            >{{ item.label }}</span>
          </a>
        </nav>
        <p class="rail-progress" aria-hidden="true">阅读进度 {{ progressPercent }}%</p>
      </template>

      <template v-else>
        <p class="rail-mid__label">栏目</p>
        <nav class="rail-categories" aria-label="栏目">
          <RouterLink
            v-for="category in categories"
            :key="category.name"
            class="rail-categories__link"
            :to="{ name: 'posts', query: { cat: category.name } }"
            :aria-current="isCategoryActive(category.name) ? 'page' : undefined"
          >
            <span class="marker-sweep" :class="{ 'is-on': isCategoryActive(category.name) }">
              {{ category.name }}
            </span>
            <span v-if="category.total" class="rail-categories__count">{{ category.total }}</span>
          </RouterLink>
        </nav>
      </template>
    </div>

    <div class="rail-search-slot"><RailSearch /></div>

    <div class="rail-foot">
      <ReadTrace />
      <p class="rail-theme">
        <span class="rail-foot__label">主题</span>
        <button type="button" class="rail-theme__btn" @click="cycleTheme">{{ themeLabel }}</button>
      </p>
    </div>
  </aside>
</template>
