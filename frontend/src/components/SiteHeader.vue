<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { useSite } from "../composables/useSite";

const route = useRoute();
const { site } = useSite();
const mobileMenuOpen = ref(false);
const isScrolled = ref(false);
const scrollProgress = ref(0);
const menuButton = ref(null);
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

/**
 * 关闭移动端菜单。
 * 模板里的 @click 会把 MouseEvent 当第一个参数传进来，因此只认布尔 true；
 * 否则每次点导航链接都会顺手抢回焦点。
 */
function closeMobileMenu(restoreFocus) {
  if (!mobileMenuOpen.value) return;
  mobileMenuOpen.value = false;
  if (restoreFocus === true) {
    menuButton.value?.focus({ preventScroll: true });
  }
}

// Esc 收起菜单并把焦点还给触发按钮：展开的面板是覆盖层，
// 键盘用户按 Esc 是唯一符合直觉的退出方式（此前只能再 Tab 回按钮）。
function onMenuKeydown(event) {
  if (event.key !== "Escape" || !mobileMenuOpen.value) return;
  event.preventDefault();
  closeMobileMenu(true);
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
  window.addEventListener("keydown", onMenuKeydown);
});

onUnmounted(() => {
  window.removeEventListener("scroll", scheduleScrollUpdate);
  window.removeEventListener("resize", scheduleScrollUpdate);
  window.removeEventListener("keydown", onMenuKeydown);
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
            :aria-current="isActive(item) ? 'page' : undefined"
          >
            <span class="print-nav__label">
              <span class="print-nav__label-text">{{ item.label }}</span>
              <svg
                class="nav-circle"
                viewBox="0 0 112 48"
                aria-hidden="true"
                focusable="false"
              >
                <path
                  class="nav-circle__stroke nav-circle__stroke--first"
                  pathLength="1"
                  d="M8 25C6 11 27 4 57 5c31 1 50 10 47 25-3 14-26 17-54 15C22 43 7 36 8 25Z"
                />
                <path
                  class="nav-circle__stroke nav-circle__stroke--second"
                  pathLength="1"
                  d="M11 22C13 8 35 3 64 7c29 4 43 15 36 28-7 12-31 13-57 9C18 40 4 30 11 22Z"
                />
              </svg>
            </span>
          </RouterLink>

          <RouterLink to="/posts" class="print-nav__item print-nav__cta" @click="closeMobileMenu">
            <span class="print-nav__label">开始阅读</span>
          </RouterLink>
        </nav>

        <button
          ref="menuButton"
          type="button"
          class="mobile-menu-button print-menu-button"
          :class="{ open: mobileMenuOpen }"
          :aria-label="menuLabel"
          :aria-expanded="mobileMenuOpen"
          aria-controls="mobile-nav-panel"
          @click="mobileMenuOpen = !mobileMenuOpen"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>
      </div>
    </div>

    <nav
      v-show="mobileMenuOpen"
      id="mobile-nav-panel"
      class="mobile-nav-panel print-mobile-nav"
      aria-label="移动端导航"
    >
      <RouterLink
        v-for="item in navLinks"
        :key="item.name"
        :to="item.to"
        :class="{ active: isActive(item) }"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click="closeMobileMenu"
      >
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
