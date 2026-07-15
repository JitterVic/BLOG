<script setup>
import { computed, onMounted } from "vue";
import { useRoute } from "vue-router";

import CursorEffects from "./components/CursorEffects.vue";
import FloatingCat from "./components/FloatingCat.vue";
import SiteHeader from "./components/SiteHeader.vue";
import { useReveal } from "./composables/useReveal";
import { useSite } from "./composables/useSite";

const route = useRoute();
const { site, ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: true });

const pageTheme = computed(() => {
  const name = route.name;
  if (name === "home") return "page-theme-home";
  if (name === "posts" || name === "post") return "page-theme-articles";
  if (name === "about") return "page-theme-about";
  return "page-theme-default";
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
          <component :is="Component" :key="viewRoute.path" />
        </Transition>
      </router-view>
    </main>

    <footer class="site-footer print-colophon">
      <div class="colophon-grid">
        <div class="colophon-brand">
          <div class="colophon__mark">{{ site?.name || "至知" }}.</div>
          <div class="colophon__issn">DIGITAL JOURNAL · 2026</div>
          <p class="colophon__headline">{{ site?.headline || "记录成长的点点滴滴" }}</p>
        </div>

        <div class="colophon-block">
          <h4>Editorial</h4>
          <ul class="colophon-list">
            <li>Flask API / Vue Frontend</li>
            <li>Markdown archive / SQLite store</li>
            <li>Designed as a printed notebook</li>
          </ul>
        </div>

        <div class="colophon-block">
          <h4>Index</h4>
          <ul class="colophon-list">
            <li>Cover / Articles / About</li>
            <li>Latest updates / Most read</li>
            <li>Built with code and paper texture</li>
          </ul>
        </div>
      </div>

      <div class="colophon__legal">
        <span>© 2026 {{ site?.name || "至知" }}</span>
        <span class="colophon__legal-sep" aria-hidden="true">·</span>
        <span>本站以报刊式视觉重新装订内容，愿每次打开都有翻阅纸页的停顿感。</span>
      </div>
    </footer>
  </div>
</template>