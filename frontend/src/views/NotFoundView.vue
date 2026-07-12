<script setup>
import { RouterLink } from "vue-router";

import { useReveal } from "../composables/useReveal";

useReveal({ reobserveOnRoute: false });
</script>

<template>
  <div class="content-view print-subpage print-not-found-page">
    <section class="print-page print-section not-found-issue">
      <div class="sec-hd rv">
        <span class="sec-hd__n">404</span>
        <h1 class="sec-hd__t">页面未收录</h1>
        <div class="sec-hd__line"></div>
      </div>

      <div class="not-found-copy">
        <p class="section-label rv">Missing Edition</p>
        <h2 class="rv" data-reveal-delay="80">这一页已经停止装订。</h2>
        <p class="rv" data-reveal-delay="140">你访问的地址不存在，或已经合并到新的文章目录中。</p>
        <div class="print-cover__actions rv" data-reveal-delay="200">
          <RouterLink to="/posts" class="cover-button primary-link">浏览文章</RouterLink>
          <RouterLink to="/" class="cover-button">返回封面</RouterLink>
        </div>
      </div>

      <span class="pg pg--r">— Not Found —</span>
    </section>
  </div>
</template>
