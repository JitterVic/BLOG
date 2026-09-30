<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

/**
 * 路由切换进度条：顶部墨色细条，模拟印刷走纸进度。
 * - 导航开始后延迟 SHOW_DELAY_MS 才显示，避免快切换时的闪烁；
 * - 进度以 trickle 方式逼近 TRICKLE_CAP，afterEach 时补满并淡出。
 */
const SHOW_DELAY_MS = 140;
const TRICKLE_INTERVAL_MS = 180;
const TRICKLE_CAP = 88;
const FINISH_FADE_MS = 320;

const router = useRouter();
const visible = ref(false);
const progress = ref(0);

let showTimer = 0;
let trickleTimer = 0;
let fadeTimer = 0;
let removeGuards = [];

function clearTimers() {
  if (showTimer) window.clearTimeout(showTimer);
  if (trickleTimer) window.clearInterval(trickleTimer);
  if (fadeTimer) window.clearTimeout(fadeTimer);
  showTimer = 0;
  trickleTimer = 0;
  fadeTimer = 0;
}

function startTrickle() {
  trickleTimer = window.setInterval(() => {
    // 越接近上限走得越慢，模拟真实网络的不确定感
    progress.value += (TRICKLE_CAP - progress.value) * 0.14;
  }, TRICKLE_INTERVAL_MS);
}

function start() {
  clearTimers();
  if (visible.value) {
    // 连续导航：直接重置进度继续走
    progress.value = 8;
    startTrickle();
    return;
  }
  showTimer = window.setTimeout(() => {
    showTimer = 0;
    progress.value = 8;
    visible.value = true;
    startTrickle();
  }, SHOW_DELAY_MS);
}

function finish() {
  if (showTimer) {
    // 尚未显示就已完成：什么都不用做
    clearTimers();
    return;
  }
  if (!visible.value) {
    clearTimers();
    return;
  }
  if (trickleTimer) {
    window.clearInterval(trickleTimer);
    trickleTimer = 0;
  }
  progress.value = 100;
  fadeTimer = window.setTimeout(() => {
    visible.value = false;
    progress.value = 0;
    fadeTimer = 0;
  }, FINISH_FADE_MS);
}

onMounted(() => {
  removeGuards = [
    router.beforeEach((to, from) => {
      if (to.fullPath !== from.fullPath) start();
      return true;
    }),
    router.afterEach(() => finish()),
    router.onError(() => finish()),
  ];
});

onBeforeUnmount(() => {
  removeGuards.forEach((remove) => remove());
  removeGuards = [];
  clearTimers();
});
</script>

<template>
  <div
    class="route-progress"
    :class="{ 'is-visible': visible, 'is-done': progress >= 100 }"
    role="progressbar"
    aria-hidden="true"
  >
    <div class="route-progress__fill" :style="{ transform: `scaleX(${progress / 100})` }"></div>
  </div>
</template>
