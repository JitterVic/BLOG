<script setup>
function scrollToTop() {
  if (typeof window === "undefined") {
    return;
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
}
</script>

<template>
  <button type="button" class="floating-cat" aria-label="回到顶部" title="回到顶部" @click="scrollToTop">
    <span class="cat-figure" aria-hidden="true">
      <span class="cat-tail"></span>
      <span class="cat-body"></span>
      <span class="cat-head">
        <span class="cat-ear cat-ear-left"></span>
        <span class="cat-ear cat-ear-right"></span>
        <span class="cat-eye cat-eye-left"></span>
        <span class="cat-eye cat-eye-right"></span>
        <span class="cat-nose"></span>
        <span class="cat-whiskers cat-whiskers-left"></span>
        <span class="cat-whiskers cat-whiskers-right"></span>
      </span>
    </span>
    <span class="cat-caption">TOP</span>
  </button>
</template>
