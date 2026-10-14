<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { MOTION_STORAGE_KEY, applyMotionClass, useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";

const route = useRoute();
const { site } = useSite();
const { refreshMotion } = useReveal({ reobserveOnRoute: false });
const mobileMenuOpen = ref(false);
const isScrolled = ref(false);
const scrollProgress = ref(0);
let scrollFrame = 0;

// 入场动效开关：默认跟随系统偏好；用户手动设置后以手动值为准。
// 用途：Windows「显示动画」关闭时 Chrome/Edge 会持续上报 prefers-reduced-motion: reduce，
// 只靠媒体查询则无法在本站重新打开动效，所以提供一个显式开关。
const readInitialMotion = () => {
  try {
    const stored = window.localStorage.getItem(MOTION_STORAGE_KEY);
    if (stored === "off") return true;
    if (stored === "on") return false;
  } catch {
    // 隐私模式：跟随系统
  }
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
};
const motionOff = ref(readInitialMotion());
const systemMotionOff = ref(readInitialMotion());

function readStoredMotion() {
  try {
    return window.localStorage.getItem(MOTION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function applyMotion(off) {
  motionOff.value = off;
  applyMotionClass(off);
}

function toggleMotion() {
  const next = !motionOff.value;
  try {
    // 手动值覆盖系统偏好；再次点击即在两态间切换
    window.localStorage.setItem(MOTION_STORAGE_KEY, next ? "off" : "on");
  } catch {
    // 隐私模式：仅本次会话生效
  }
  applyMotion(next);
  refreshMotion();
}

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
  // 与 main.js 的初始判定对齐：main.js 已在挂载前打过标，这里只做补正。
  const stored = readStoredMotion();
  applyMotion(stored === "off" ? true : stored === "on" ? false : systemMotionOff.value);
});

// 系统偏好变化时同步（用户没手动设置过才跟随）
const motionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)");
function onSystemMotionChange(event) {
  systemMotionOff.value = event.matches;
  if (readStoredMotion() === null) applyMotion(event.matches);
}
motionQuery?.addEventListener?.("change", onSystemMotionChange);

onUnmounted(() => {
  window.removeEventListener("scroll", scheduleScrollUpdate);
  window.removeEventListener("resize", scheduleScrollUpdate);
  if (scrollFrame) window.cancelAnimationFrame(scrollFrame);
  motionQuery?.removeEventListener?.("change", onSystemMotionChange);
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

          <button
            type="button"
            class="print-nav__item print-nav__motion"
            :class="{ 'is-off': motionOff }"
            :aria-pressed="motionOff ? 'true' : 'false'"
            :title="motionOff ? '开启入场动效' : '关闭入场动效'"
            :aria-label="motionOff ? '开启入场动效' : '关闭入场动效'"
            @click="toggleMotion"
          >
            <span class="print-nav__label">{{ motionOff ? "动效关" : "动效开" }}</span>
          </button>
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
      <button type="button" class="print-mobile-nav__motion" :aria-pressed="motionOff ? 'true' : 'false'" @click="toggleMotion">
        <span>{{ motionOff ? "○" : "●" }}</span>
        <strong>{{ motionOff ? "动效关闭" : "动效开启" }}</strong>
        <small>Motion</small>
      </button>
    </nav>
  </header>
</template>
