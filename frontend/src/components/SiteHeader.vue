<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { useSite } from "../composables/useSite";

const route = useRoute();
const { site } = useSite();
const mobileMenuOpen = ref(false);
const isScrolled = ref(false);

const navLinks = [
  { name: "home", to: "/", label: "封面", english: "Cover" },
  { name: "posts", to: "/posts", label: "文章", english: "Articles", aliases: ["post"] },
  { name: "about", to: "/about", label: "关于", english: "About" },
];

const isActive = (item) => item.name === route.name || item.aliases?.includes(route.name);
const menuLabel = computed(() => (mobileMenuOpen.value ? "关闭导航菜单" : "打开导航菜单"));
const brandName = computed(() => site.value?.name || "至知");

function closeMobileMenu() {
  mobileMenuOpen.value = false;
}

function updateScrolledState() {
  isScrolled.value = window.scrollY > 24;
}

watch(
  () => route.fullPath,
  () => closeMobileMenu(),
);

onMounted(() => {
  updateScrolledState();
  window.addEventListener("scroll", updateScrolledState, { passive: true });
});

onUnmounted(() => {
  window.removeEventListener("scroll", updateScrolledState);
});
</script>

<template>
  <header class="site-header print-nav" :class="{ scrolled: isScrolled, 'menu-open': mobileMenuOpen }">
    <RouterLink to="/" class="print-nav__brand" @click="closeMobileMenu">
      <span>{{ brandName }}</span><i>.</i>
    </RouterLink>

    <nav class="print-nav__links desktop-nav" aria-label="主导航">
      <RouterLink
        v-for="(item, index) in navLinks"
        :key="item.name"
        :to="item.to"
        class="print-nav__item"
        :class="{ active: isActive(item) }"
      >
        <span class="print-nav__num">{{ String(index + 1).padStart(2, "0") }}</span>
        <span class="print-nav__label">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="header-tools print-nav__tools">
      <RouterLink to="/posts" class="header-cta print-read-link" @click="closeMobileMenu">
        开始阅读
      </RouterLink>
      <button
        type="button"
        class="mobile-menu-button print-menu-button"
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

    <nav v-if="mobileMenuOpen" class="mobile-nav-panel print-mobile-nav" aria-label="移动端导航">
      <RouterLink
        v-for="(item, index) in navLinks"
        :key="item.name"
        :to="item.to"
        :class="{ active: isActive(item) }"
        @click="closeMobileMenu"
      >
        <span>{{ String(index + 1).padStart(2, "0") }}</span>
        <strong>{{ item.label }}</strong>
        <small>{{ item.english }}</small>
      </RouterLink>
    </nav>
  </header>
</template>
