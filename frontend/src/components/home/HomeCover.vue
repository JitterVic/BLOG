<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";

import SplitText from "../SplitText.vue";
import { usePageFlip } from "../../composables/usePageFlip";
import { useSite } from "../../composables/useSite";

defineProps({
  // 本期要目：最新三篇，由 HomeView 在数据就位后传入；空数组时整块不渲染
  posts: { type: Array, default: () => [] },
});

const { site } = useSite();
const { navigateToPage } = usePageFlip();

const issueMonth = computed(() => new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
}).format(new Date()));
const issueNumber = computed(() => String(new Date().getMonth() + 1).padStart(2, "0"));
</script>

<template>
  <section id="cover" class="print-page print-cover focused-cover" style="--i: 0" aria-label="首页封面">
    <span class="bg-issue-num" aria-hidden="true">001</span>

    <div class="print-cover__masthead rv" data-reveal-delay="0">
      <span>Vol. {{ issueNumber }} · Digital Edition</span>
      <span>{{ issueMonth }}</span>
    </div>

    <div class="focused-cover__body">
      <p class="cover-kicker rv" data-reveal-delay="40">Personal Technical Journal</p>
      <h1 class="rv cover-title" data-reveal-delay="80">
        <SplitText :text="site?.name || '至知'" :base-delay="140" :step="90" /><br>
        <SplitText text="Journal" tag="em" :base-delay="420" :step="52" />
      </h1>
      <div class="print-accent-rule rv" data-reveal-delay="160" aria-hidden="true"></div>
      <p class="print-cover__summary rv" data-reveal-delay="220">
        {{ site?.headline || "报刊式排版重装技术笔记。" }}
      </p>

      <div class="focused-cover__actions rv" data-reveal-delay="280" aria-label="首页文章入口">
        <a href="#latest" class="cover-button primary-link" data-cursor="翻阅" @click="navigateToPage(1, $event)">最近更新</a>
        <a href="#hot" class="cover-button" data-cursor="翻阅" @click="navigateToPage(2, $event)">热点文章</a>
        <RouterLink to="/posts" class="cover-button ghost-link" data-cursor="目录">全部目录</RouterLink>
      </div>

      <!-- 本期要目：首屏从「只能翻页」变成「有内容可点」。
           数据未就位时整块不渲染，就位后随 reveal 入场。 -->
      <nav v-if="posts.length" class="cover-toc rv" data-reveal-delay="360" aria-label="本期要目">
        <span class="cover-toc__label">本期要目 · In This Issue</span>
        <ol class="cover-toc__list" :style="{ '--toc-cols': Math.min(posts.length, 3) }">
          <li v-for="(post, index) in posts.slice(0, 3)" :key="post.slug">
            <RouterLink :to="`/posts/${post.slug}`" data-cursor="阅读">
              <span class="cover-toc__no">{{ String(index + 1).padStart(2, "0") }}</span>
              <span class="cover-toc__title">{{ post.title }}</span>
              <span class="cover-toc__cat">{{ post.category || "Article" }}</span>
            </RouterLink>
          </li>
        </ol>
      </nav>
    </div>


    <a class="print-scroll-cue" href="#latest" data-cursor="翻阅" @click="navigateToPage(1, $event)">
      <span class="print-scroll-cue__icon" aria-hidden="true">↓</span>
      <span>向下翻阅 · Scroll to explore</span>
    </a>
    <span class="pg pg--r">— 001 —</span>
  </section>
</template>
