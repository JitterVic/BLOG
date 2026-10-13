<script setup>
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";

import { displayDate } from "../../composables/useFormat";

defineProps({
  post: { type: Object, required: true },
});

const featureCardRef = ref(null);
const issueNumber = computed(() => String(new Date().getMonth() + 1).padStart(2, "0"));

/**
 * RouterLink 上拿到的 ref 是组件实例，没有 getBoundingClientRect，
 * 需要一个真正的 DOM 元素引用；同时兼容未来换成原生元素的情况。
 */
function cardElement() {
  const target = featureCardRef.value;
  return target?.$el || target;
}

function handlePointerMove(e) {
  const el = cardElement();
  if (!el || e.pointerType === "touch") return;
  const rect = el.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const centerX = rect.width / 2;
  const centerY = rect.height / 2;
  const tiltX = -((y - centerY) / centerY) * 4.5;
  const tiltY = ((x - centerX) / centerX) * 4.5;

  el.style.setProperty("--feature-tilt-x", `${tiltX.toFixed(2)}deg`);
  el.style.setProperty("--feature-tilt-y", `${tiltY.toFixed(2)}deg`);
  el.style.setProperty("--feature-x", `${((x / rect.width) * 100).toFixed(1)}%`);
  el.style.setProperty("--feature-y", `${((y / rect.height) * 100).toFixed(1)}%`);
}

function handlePointerLeave() {
  const el = cardElement();
  if (!el) return;
  el.style.setProperty("--feature-tilt-x", "0deg");
  el.style.setProperty("--feature-tilt-y", "0deg");
  el.style.setProperty("--feature-x", "50%");
  el.style.setProperty("--feature-y", "50%");
}
</script>

<template>
  <div class="g2 home-latest-feature" data-feature-card="latest">
    <RouterLink
      ref="featureCardRef"
      :to="`/posts/${post.slug}`"
      class="mimg print-feature-image rv"
      :class="{ 'mimg--has-image': !!post.cover_image }"
      data-reveal-delay="40"
      @pointermove="handlePointerMove"
      @pointerleave="handlePointerLeave"
    >
      <img
        v-if="post.cover_image"
        class="mimg__img"
        :src="post.cover_image"
        alt=""
        width="960"
        height="640"
        loading="eager"
        fetchpriority="high"
        decoding="async"
        @error="(event) => event.target.classList.add('is-broken')"
      >
      <div class="feature-spotlight" aria-hidden="true"></div>
      <div class="feature-poster-mark" aria-hidden="true">
        <span>NEW</span>
        <strong>01</strong>
      </div>
      <div class="feature-orbit" aria-hidden="true">
        <i></i><i></i><i></i>
      </div>
      <div class="print-feature-art">
        <div class="feature-tags">
          <span
            v-for="tag in post.tags?.slice(0, 3)"
            :key="tag"
            class="tag tag--code"
          >{{ tag }}</span>
        </div>
        <span class="feature-kicker">Editor’s pick · 最新一期</span>
        <h2>{{ post.title }}</h2>
        <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
        <span class="feature-open-hint" aria-hidden="true">打开文章 <b>↗</b></span>
      </div>
      <div class="mimg__cap">cover story — {{ displayDate(post.published_at) }}</div>
    </RouterLink>

    <article class="art print-lead-copy rv" data-reveal-delay="120">
      <div class="print-lead-copy__inner">
        <div class="lead-issue-line">
          <div class="art__cat">Latest Issue</div>
          <span>Vol. {{ issueNumber }}</span>
        </div>
        <h3 class="art__t art__t--xl">{{ post.title }}</h3>
        <p class="art__p">{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
        <div class="art__meta">
          <span>{{ post.category || "Article" }}</span>
          <span>{{ post.read_time }}</span>
          <span>{{ displayDate(post.published_at) }}</span>
        </div>
        <RouterLink :to="`/posts/${post.slug}`" class="text-link print-read-more">
          阅读全文 →
        </RouterLink>
      </div>
    </article>
  </div>
</template>
