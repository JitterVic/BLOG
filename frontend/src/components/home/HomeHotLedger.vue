<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { displayDate, formatClicks } from "../../composables/useFormat";

defineProps({
  posts: { type: Array, required: true },
});

/**
 * 阅读量 count-up：行随 reveal 进入视口时，数字从 0 滚到实际值（650ms，三次方缓出）。
 * 实现要点：
 * - 模板里渲染的是真实值，IO 触发前用户看到的是终态，触发那一刻行还在
 *   reveal 的淡入期（透明度接近 0），重写成 0 再滚动不会穿帮；
 * - reduced-motion 下直接不启动观察，数字保持终态；
 * - 每行只播一次。
 */
const ledgerRef = ref(null);
let observer = null;

function playCountUp(el) {
  const target = Number(el.dataset.count || 0);
  if (!target) return;
  const duration = 650;
  const start = performance.now();
  const tick = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = formatClicks(Math.round(target * eased));
    if (progress < 1) window.requestAnimationFrame(tick);
  };
  window.requestAnimationFrame(tick);
}

onMounted(() => {
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        playCountUp(entry.target);
        observer.unobserve(entry.target);
      }
    },
    { threshold: 0.4 },
  );
  ledgerRef.value
    ?.querySelectorAll(".home-hot-row__clicks")
    .forEach((el) => observer.observe(el));
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
});
</script>

<template>
  <div ref="ledgerRef" class="home-hot-ledger">
    <p class="home-hot-ledger__caption">Most Read · 按阅读量排序</p>
    <RouterLink
      v-for="(post, index) in posts"
      :key="post.slug"
      :to="`/posts/${post.slug}`"
      class="home-hot-row rv"
      data-cursor="阅读"
      :data-reveal-delay="index * 70"
    >
      <span class="home-hot-row__rank">{{ String(index + 1).padStart(2, "0") }}</span>
      <div class="home-hot-row__copy">
        <div class="home-hot-row__titleline">
          <h3>{{ post.title }}</h3>
          <!-- 点线 leader：把阅读量牵到行尾，避免视线横跨整行去寻找 -->
          <span class="home-hot-row__leader" aria-hidden="true"></span>
          <strong class="home-hot-row__clicks" :data-count="post.click_count || 0">{{ formatClicks(post.click_count) }}</strong>
        </div>
        <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
        <div class="home-hot-row__foot">
          <span class="home-hot-row__cat">{{ post.category || "Most Read" }}</span>
          <span>{{ displayDate(post.published_at) }}</span>
        </div>
      </div>
    </RouterLink>
  </div>
</template>
