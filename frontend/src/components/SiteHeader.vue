<script setup>
import { computed, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { useSite } from "../composables/useSite";

const route = useRoute();
const { site } = useSite();
const mobileMenuOpen = ref(false);

const navLinks = [
  { name: "home", to: "/", label: "首页" },
  { name: "posts", to: "/posts", label: "文章", aliases: ["post"] },
  { name: "archive", to: "/archive", label: "归档" },
  { name: "tags", to: "/tags", label: "标签" },
  { name: "about", to: "/about", label: "关于" },
];

const isActive = (item) => item.name === route.name || item.aliases?.includes(route.name);
const menuLabel = computed(() => (mobileMenuOpen.value ? "关闭导航菜单" : "打开导航菜单"));

function closeMobileMenu() {
  mobileMenuOpen.value = false;
}

watch(
  () => route.fullPath,
  () => closeMobileMenu(),
);
</script>

<template>
  <header class="site-header">
    <div class="header-left">
      <RouterLink to="/" class="brand-block" @click="closeMobileMenu">
        <span class="brand-dot" aria-hidden="true"></span>
        <strong>{{ site?.name || "至知" }}</strong>
      </RouterLink>
    </div>

    <nav class="top-nav desktop-nav" aria-label="主导航">
      <RouterLink
        v-for="item in navLinks"
        :key="item.name"
        :to="item.to"
        :class="{ active: isActive(item) }"
      >
        {{ item.label }}
      </RouterLink>
    </nav>

    <div class="header-tools">
      <RouterLink to="/posts" class="header-cta" @click="closeMobileMenu">开始阅读</RouterLink>
      <button
        type="button"
        class="mobile-menu-button"
        :class="{ open: mobileMenuOpen }"
        :aria-label="menuLabel"
        :aria-expanded="mobileMenuOpen"
        @click="mobileMenuOpen = !mobileMenuOpen"
      >
        <span></span>
        <span></span>
        <span></span>
      </button>
    </div>

    <nav v-if="mobileMenuOpen" class="mobile-nav-panel" aria-label="移动端导航">
      <RouterLink
        v-for="item in navLinks"
        :key="item.name"
        :to="item.to"
        :class="{ active: isActive(item) }"
        @click="closeMobileMenu"
      >
        {{ item.label }}
      </RouterLink>
    </nav>
  </header>
</template>
