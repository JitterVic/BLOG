<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";

import { useSite } from "../../composables/useSite";

const { site } = useSite();

const issueMonth = computed(() => new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
}).format(new Date()));
const issueNumber = computed(() => String(new Date().getMonth() + 1).padStart(2, "0"));
</script>

<template>
  <section id="cover" class="print-page print-cover focused-cover" aria-label="首页封面">
    <div class="print-cover__masthead rv" data-reveal-delay="0">
      <span>Vol. {{ issueNumber }} · Digital Edition</span>
      <span>{{ issueMonth }}</span>
    </div>

    <div class="focused-cover__body">
      <p class="cover-kicker rv" data-reveal-delay="40">Personal Technical Journal</p>
      <h1 class="rv cover-title" data-reveal-delay="80">
        {{ site?.name || "至知" }}<br>
        <em>Journal</em>
      </h1>
      <div class="print-accent-rule rv" data-reveal-delay="160" aria-hidden="true"></div>
      <p class="print-cover__summary rv" data-reveal-delay="220">
        {{ site?.headline || "以报刊式排版重装技术笔记，让阅读再次拥有翻页的停顿感。" }}
      </p>

      <div class="focused-cover__actions rv" data-reveal-delay="280" aria-label="首页文章入口">
        <a href="#latest" class="cover-button primary-link">最近更新</a>
        <a href="#hot" class="cover-button">热点文章</a>
        <RouterLink to="/posts" class="cover-button ghost-link">全部目录</RouterLink>
      </div>
    </div>

    <a class="print-scroll-cue" href="#latest">
      <span class="print-scroll-cue__icon" aria-hidden="true">↓</span>
      <span>向下翻阅 · Scroll to explore</span>
    </a>
    <span class="pg pg--r">— 001 —</span>
  </section>
</template>
