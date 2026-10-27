<script setup>
// 左栏（DESIGN.md §4.2，≥ 1100px）：回答「我在哪」「附近有什么」。
// 列表页里它是栏目索引；文章页里它是栏目文章目录（本栏目各篇，当前篇高亮），
// 本文目录在文章页右栏批注栏。左栏可在文章页整栏收起（书脊页签展开）。

import { computed } from "vue";
import { useRoute } from "vue-router";
import { RouterLink } from "vue-router";

import RailSearch from "./RailSearch.vue";
import ReadTrace from "./ReadTrace.vue";
import { NOTE_TYPES } from "../composables/useNotes";
import { useDeskPanels } from "../composables/useDeskPanels";
import { useRailState } from "../composables/useRailState";
import { useReadLog } from "../composables/useReadLog";
import { useSite } from "../composables/useSite";
import { useTheme } from "../composables/useTheme";

const route = useRoute();
const { site } = useSite();
const { articleSiblings, articleCategory } = useRailState();
const { isRead } = useReadLog();
const { toggleRail } = useDeskPanels();
const { label: themeLabel, cycle: cycleTheme } = useTheme();

const isPost = computed(() => route.name === "post");
const isNotesSection = computed(() => route.name === "notes" || route.name === "note");

const NAV_ITEMS = [
  { name: "home", label: "首页", to: "/" },
  { name: "posts", label: "文章", to: "/posts" },
  { name: "notes", label: "余笺", to: "/notes" },
  { name: "about", label: "关于", to: "/about" },
];

const backToCategory = computed(() => ({
  label: "返回",
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
  if (name === "notes") return route.name === "notes" || route.name === "note";
  return route.name === name || (name === "posts" && route.name === "post");
}

function isCategoryActive(name) {
  return route.name === "posts" && route.query.cat === name;
}

function isNoteTypeActive(typeValue) {
  if (route.name !== "notes") return false;
  const raw = typeof route.query.type === "string" ? route.query.type : "";
  return raw === typeValue;
}

/** 目录项状态：当前篇套荧光扫过，已读套荧光笔，其余素色。 */
function siblingClass(slug) {
  if (slug === route.params.slug) return "marker-sweep is-on";
  if (isRead(slug)) return "marker";
  return "";
}
</script>

<template>
  <aside class="rail">
    <p class="rail-brand">
      <RouterLink class="rail-brand__link" to="/">至知</RouterLink>
      <button
        v-if="isPost"
        type="button"
        class="panel-collapse"
        @click="toggleRail(true)"
      >‹ 收起</button>
    </p>

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
      <template v-else>
        <RouterLink class="rail-nav__link rail-nav__back" :to="backToCategory.to">
          {{ backToCategory.label }}
        </RouterLink>
        <div class="rail-nav__mini" aria-label="快捷导航">
          <RouterLink
            v-for="item in NAV_ITEMS"
            :key="item.name"
            class="rail-nav__mini-link"
            :to="item.to"
          >{{ item.label }}</RouterLink>
        </div>
      </template>
    </nav>

    <div class="rail-mid">
      <!-- 文章页：栏目文章目录（本栏目各篇，当前篇高亮；本文目录在右栏批注栏） -->
      <template v-if="isPost && articleSiblings.length">
        <p class="rail-mid__label">{{ articleCategory }} · {{ articleSiblings.length }} 篇</p>
        <nav class="rail-siblings" :aria-label="`${articleCategory} 栏目文章目录`">
          <template v-for="item in articleSiblings" :key="item.slug">
            <span
              v-if="item.slug === route.params.slug"
              class="rail-siblings__link"
              aria-current="page"
            >
              <span class="marker-sweep is-on">{{ item.title }}</span>
              <span class="sr-only">（当前篇目）</span>
            </span>
            <RouterLink
              v-else
              class="rail-siblings__link"
              :to="{ name: 'post', params: { slug: item.slug } }"
            >
              <span :class="siblingClass(item.slug)">{{ item.title }}</span>
            </RouterLink>
          </template>
        </nav>
      </template>

      <template v-else-if="isNotesSection">
        <p class="rail-mid__label">余笺类型</p>
        <nav class="rail-categories" aria-label="余笺类型">
          <RouterLink
            v-for="item in NOTE_TYPES"
            :key="item.value || 'all'"
            class="rail-categories__link"
            :to="{ name: 'notes', query: item.value ? { type: item.value } : {} }"
            :aria-current="isNoteTypeActive(item.value) ? 'page' : undefined"
          >
            <span class="marker-sweep" :class="{ 'is-on': isNoteTypeActive(item.value) }">
              {{ item.label }}
            </span>
          </RouterLink>
        </nav>
      </template>

      <template v-else>
        <p class="rail-mid__label">栏目</p>
        <nav class="rail-categories" aria-label="栏目">
          <RouterLink
            v-if="route.name === 'posts'"
            class="rail-categories__link"
            :to="{ name: 'posts' }"
            :aria-current="!route.query.cat ? 'page' : undefined"
          >
            <span class="marker-sweep" :class="{ 'is-on': !route.query.cat }">全部</span>
          </RouterLink>
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
