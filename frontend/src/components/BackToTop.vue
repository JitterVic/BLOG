<script setup>
// 回顶 BackToTop（长页按需浮现）：滚动超过 600px 才出现，固定视口右下角。
// 标准次级按钮规格（36px 高、1px 控件线、纸底），无阴影、非圆形悬浮球；印刷不带走。

import { onBeforeUnmount, onMounted, ref } from "vue";

const visible = ref(false);

function onScroll() {
  visible.value = window.scrollY > 600;
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
}

onMounted(() => window.addEventListener("scroll", onScroll, { passive: true }));
onBeforeUnmount(() => window.removeEventListener("scroll", onScroll));
</script>

<template>
  <Transition name="backtop">
    <button v-if="visible" type="button" class="back-to-top" @click="scrollToTop">↑ 顶部</button>
  </Transition>
</template>
