<script setup>
import { onBeforeUnmount, ref } from "vue";

import { dispatchGoTopEvent } from "../constants/events";

const isJumping = ref(false);
let jumpTimer = 0;

const JUMP_DURATION_MS = 820;
const REDUCED_MOTION_JUMP_DURATION_MS = 120;

function resetJump() {
  isJumping.value = false;
  jumpTimer = 0;
}

function clearJumpTimer() {
  if (!jumpTimer) {
    return;
  }

  window.clearTimeout(jumpTimer);
  jumpTimer = 0;
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function scheduleJumpReset(reducedMotion) {
  jumpTimer = window.setTimeout(
    resetJump,
    reducedMotion ? REDUCED_MOTION_JUMP_DURATION_MS : JUMP_DURATION_MS,
  );
}

function scrollToTop() {
  if (typeof window === "undefined") {
    return;
  }

  clearJumpTimer();

  isJumping.value = true;
  dispatchGoTopEvent();

  const reducedMotion = prefersReducedMotion();
  window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
  scheduleJumpReset(reducedMotion);
}

onBeforeUnmount(() => {
  clearJumpTimer();
});
</script>

<template>
  <button
    type="button"
    class="floating-cat"
    :class="{ 'is-jumping': isJumping }"
    aria-label="回到顶部"
    title="回到顶部"
    @click="scrollToTop"
  >
    <span class="cat-figure" aria-hidden="true">
      <span class="cat-tail"></span>
      <span class="cat-body"></span>
      <span class="cat-head">
        <span class="cat-ear cat-ear-left"></span>
        <span class="cat-ear cat-ear-right"></span>
        <span class="cat-eye cat-eye-left"></span>
        <span class="cat-eye cat-eye-right"></span>
        <span class="cat-blush cat-blush-left"></span>
        <span class="cat-blush cat-blush-right"></span>
        <span class="cat-nose"></span>
        <span class="cat-whiskers cat-whiskers-left"></span>
        <span class="cat-whiskers cat-whiskers-right"></span>
      </span>
      <span class="cat-paw cat-paw-left"></span>
      <span class="cat-paw cat-paw-right"></span>
    </span>
    <span class="cat-caption">TOP</span>
  </button>
</template>
