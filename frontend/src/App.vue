<script setup>
import { onMounted } from "vue";

import CursorEffects from "./components/CursorEffects.vue";
import FloatingCat from "./components/FloatingCat.vue";
import SiteHeader from "./components/SiteHeader.vue";
import { useSite } from "./composables/useSite";

const { site, ensureSite } = useSite();

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // The child views handle their own fallback UI.
  }
});
</script>

<template>
  <div class="page-shell">
    <CursorEffects />
    <FloatingCat />
    <SiteHeader />

    <main class="app-main">
      <router-view />
    </main>

    <footer class="site-footer">
      <p>{{ site?.name || "至知" }}</p>
      <span>Built with Flask + Vue.</span>
    </footer>
  </div>
</template>
