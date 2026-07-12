<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { useSite } from "../composables/useSite";

const route = useRoute();
const { site } = useSite();
const mobileMenuOpen = ref(false);
const isScrolled = ref(false);
const scrollProgress = ref(0);
let scrollFrame = 0;

const navLinks = [
  { name: "home", to: "/", label: "封面", english: "Cover" },
  { name: "posts", to: "/posts", label: "文章", english: "Articles", aliases: ["post"] },
  { name: "about", to: "/about", label: "关于", english: "About" },
];

const isActive = (item) => item.name === route.name || item.aliases?.includes(route.name);
const menuLabel = computed(() => (mobileMenuOpen.value ? "关闭导航菜单" : "打开导航菜单"));
const brandName = computed(() => site.value?.name || "至知");
const progressStyle = computed(() => ({
  transform: `scaleX(${scrollProgress.value})`,
}));

function closeMobileMenu() {
  mobileMenuOpen.value = false;
}

function updateScrollState() {
  const y = window.scrollY || 0;
  isScrolled.value = y > 18;
  const doc = document.documentElement;
  const max = Math.max(doc.scrollHeight - window.innerHeight, 1);
  scrollProgress.value = Math.min(Math.max(y / max, 0), 1);
}

function scheduleScrollUpdate() {
  if (scrollFrame) return;
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = 0;
    updateScrollState();
  });
}

watch(
  () => route.fullPath,
  () => {
    closeMobileMenu();
    scheduleScrollUpdate();
  },
);

onMounted(() => {
  updateScrollState();
  window.addEventListener("scroll", scheduleScrollUpdate, { passive: true });
  window.addEventListener("resize", scheduleScrollUpdate, { passive: true });
});

onUnmounted(() => {
  window.removeEventListener("scroll", scheduleScrollUpdate);
  window.removeEventListener("resize", scheduleScrollUpdate);
  if (scrollFrame) window.cancelAnimationFrame(scrollFrame);
});
</script>

<template>
  <header
    class="site-header print-nav"
    :class="{ scrolled: isScrolled, 'menu-open': mobileMenuOpen }"
  >
    <div class="print-nav__progress" aria-hidden="true">
      <span :style="progressStyle"></span>
    </div>

    <div class="print-nav__inner">
      <RouterLink to="/" class="print-nav__brand" @click="closeMobileMenu">
        <span>{{ brandName }}</span><i>.</i>
      </RouterLink>

      <div class="print-nav__right">
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

          <RouterLink to="/posts" class="print-nav__item print-nav__cta" @click="closeMobileMenu">
            <span class="print-nav__label">开始阅读</span>
          </RouterLink>
        </nav>

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
    </div>

    <nav
      v-if="mobileMenuOpen"
      class="mobile-nav-panel print-mobile-nav"
      aria-label="移动端导航"
    >
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
      <RouterLink to="/posts" @click="closeMobileMenu">
        <span>→</span>
        <strong>开始阅读</strong>
        <small>Articles</small>
      </RouterLink>
    </nav>
  </header>
</template>
