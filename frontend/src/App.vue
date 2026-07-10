<script setup>
import { onMounted } from "vue";

import CursorEffects from "./components/CursorEffects.vue";
import FloatingCat from "./components/FloatingCat.vue";
import PrintParticles from "./components/PrintParticles.vue";
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
  <div class="page-shell print-shell">
    <PrintParticles />
    <CursorEffects />
    <FloatingCat />
    <SiteHeader />

    <main class="app-main print-main">
      <router-view />
    </main>

    <footer class="site-footer print-colophon">
      <div>
        <div class="colophon__mark">{{ site?.name || "至知" }}.</div>
        <div class="colophon__issn">DIGITAL JOURNAL · 2026</div>
        <p>{{ site?.headline || "记录成长的点点滴滴" }}</p>
      </div>
      <div>
        <h4>Editorial</h4>
        <p>Flask API / Vue Frontend<br>Markdown archive / SQLite store<br>Designed as a printed notebook.</p>
      </div>
      <div>
        <h4>Index</h4>
        <p>Cover / Articles / About<br>Latest updates / Most read<br>Built with code and paper texture.</p>
      </div>
      <div class="colophon__legal">
        © 2026 {{ site?.name || "至知" }}. 本站以报刊式视觉重新装订内容，愿每次打开都有翻阅纸页的停顿感。
      </div>
    </footer>
  </div>
</template>
