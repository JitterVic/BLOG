<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { useSite } from "../composables/useSite";
import SplitText from "./SplitText.vue";

/**
 * 首屏 Loader（数据感知版）：
 * - 进度以 trickle 方式逼近 TRICKLE_CAP，等待站点数据真正就绪后补满；
 * - 至少展示 MIN_DISPLAY_MS 保证逐字动画完整，最多 MAX_WAIT_MS 兜底放行；
 * - 与 index.html 中的内联 boot-splash 视觉无缝衔接。
 */
const MIN_DISPLAY_MS = 1150;
const MAX_WAIT_MS = 6000;
const FINISH_HOLD_MS = 420;
const TRICKLE_INTERVAL_MS = 120;
const TRICKLE_CAP = 92;

const STAGES = [
  { until: 34, caption: "正在校对样张……" },
  { until: 68, caption: "铅字排版中……" },
  { until: 101, caption: "装订成刊……" },
];
const DONE_CAPTION = "开卷有益 · Enjoy Reading";

const emit = defineEmits(["ready"]);

const { site, error, ensureSite } = useSite();

const isVisible = ref(true);
const isMounted = ref(false);
const progress = ref(0);
const dataReady = ref(false);

let startTime = 0;
let trickleTimer = 0;
let finishTimer = 0;
let hideTimer = 0;
let maxTimer = 0;
let finishing = false;

const caption = computed(() => {
  if (progress.value >= 100) return DONE_CAPTION;
  const stage = STAGES.find((item) => progress.value < item.until);
  return (stage || STAGES[STAGES.length - 1]).caption;
});

const percentText = computed(() => `${String(Math.round(progress.value)).padStart(2, "0")}%`);
const fillStyle = computed(() => ({ transform: `scaleX(${progress.value / 100})` }));

function clearTimers() {
  [trickleTimer, finishTimer, hideTimer, maxTimer].forEach((timer) => {
    if (timer) {
      window.clearTimeout(timer);
      window.clearInterval(timer);
    }
  });
  trickleTimer = 0;
  finishTimer = 0;
  hideTimer = 0;
  maxTimer = 0;
}

function hide() {
  if (!isVisible.value) return;
  clearTimers();
  isVisible.value = false;
  emit("ready");
}

function tryFinish() {
  if (finishing || !dataReady.value) return;
  finishing = true;

  const elapsed = performance.now() - startTime;
  const wait = Math.max(MIN_DISPLAY_MS - elapsed, 0);

  finishTimer = window.setTimeout(() => {
    if (trickleTimer) {
      window.clearInterval(trickleTimer);
      trickleTimer = 0;
    }
    progress.value = 100;
    hideTimer = window.setTimeout(hide, FINISH_HOLD_MS);
  }, wait);
}

function markDataReady() {
  if (dataReady.value) return;
  dataReady.value = true;
  tryFinish();
}

onMounted(() => {
  startTime = performance.now();
  isMounted.value = true;

  // 慢速逼近 TRICKLE_CAP，数据未就绪时也不会卡在 0
  trickleTimer = window.setInterval(() => {
    progress.value += (TRICKLE_CAP - progress.value) * 0.075;
  }, TRICKLE_INTERVAL_MS);

  // 与 App.vue 共享单例请求；已缓存则直接就绪
  if (site.value || error.value) {
    markDataReady();
  } else {
    ensureSite().catch(() => {
      // error 状态由 useSite 记录，watch 会触发收尾
    });
  }

  // 兜底：任何异常都不允许 Loader 永久遮挡内容
  maxTimer = window.setTimeout(hide, MAX_WAIT_MS);
});

watch([site, error], ([siteValue, errorValue]) => {
  if (siteValue || errorValue) markDataReady();
});

onBeforeUnmount(() => {
  clearTimers();
});
</script>

<template>
  <Transition name="journal-loader">
    <div v-if="isVisible" class="journal-initial-loader" aria-hidden="true">
      <div class="loader-content" :class="{ 'is-active': isMounted }">
        <div class="loader-masthead">
          <span>VOL. 03 · DIGITAL EDITION</span>
          <span class="loader-dot">·</span>
          <span>EST. 2026</span>
        </div>

        <h1 class="loader-title">
          <SplitText text="至知" :base-delay="120" :step="90" />
          <SplitText text="Journal" tag="em" :base-delay="380" :step="52" />
        </h1>

        <div class="loader-ink-bar">
          <div class="loader-ink-fill" :style="fillStyle"></div>
        </div>

        <div class="loader-caption">
          <span class="loader-spinner" :class="{ 'is-done': progress >= 100 }"></span>
          <span class="loader-caption__text">{{ caption }}</span>
          <span class="loader-percent">{{ percentText }}</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.journal-initial-loader {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: grid;
  place-items: center;
  background: var(--paper, #f6f1e8);
  color: var(--ink, #1c1710);
  pointer-events: all;
  overflow: hidden;
}

.journal-initial-loader::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle, rgba(42, 36, 28, 0.14) 0.5px, transparent 0.6px),
    linear-gradient(90deg, rgba(42, 36, 28, 0.015), transparent 50%, rgba(255, 255, 255, 0.025));
  background-size: 4px 4px, 100% 100%;
  opacity: 0.22;
  mix-blend-mode: multiply;
  pointer-events: none;
}

.loader-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 2rem;
}

.loader-masthead {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-family: var(--f-mono, monospace);
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: var(--accent, #8b2500);
  text-transform: uppercase;
  margin-bottom: 0.6rem;
  opacity: 0;
  transform: translate3d(0, 10px, 0);
  transition:
    opacity 0.45s var(--ease-quart, cubic-bezier(0.25, 1, 0.5, 1)) 0.05s,
    transform 0.55s var(--ease-expo, cubic-bezier(0.16, 1, 0.3, 1)) 0.05s;
}

.loader-content.is-active .loader-masthead {
  opacity: 1;
  transform: translate3d(0, 0, 0);
}

.loader-dot {
  opacity: 0.5;
}

.loader-title {
  display: flex;
  align-items: baseline;
  gap: 0.35em;
  margin: 0 0 1.2rem;
  font-family: var(--f-display, "Playfair Display", serif);
  font-size: clamp(2.4rem, 6vw, 3.8rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--ink, #1c1710);
}

.loader-title :deep(em) {
  font-style: italic;
  font-weight: 400;
  color: var(--ink-light, #5e5548);
}

.loader-ink-bar {
  position: relative;
  width: min(240px, 60vw);
  height: 2px;
  background: rgba(42, 36, 28, 0.12);
  margin-bottom: 1.2rem;
  overflow: hidden;
  border-radius: 1px;
  opacity: 0;
  transition: opacity 0.4s ease 0.3s;
}

.loader-content.is-active .loader-ink-bar {
  opacity: 1;
}

.loader-ink-fill {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, var(--accent, #8b2500), var(--accent-light, #b84a2a));
  transform-origin: left center;
  transform: scaleX(0);
  transition: transform 0.32s var(--ease-quart, cubic-bezier(0.25, 1, 0.5, 1));
}

.loader-caption {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-family: var(--f-mono, monospace);
  font-size: 0.62rem;
  letter-spacing: 0.12em;
  color: var(--ink-faded, #8a7f6f);
  opacity: 0;
  transform: translate3d(0, 8px, 0);
  transition:
    opacity 0.45s var(--ease-quart, cubic-bezier(0.25, 1, 0.5, 1)) 0.5s,
    transform 0.55s var(--ease-expo, cubic-bezier(0.16, 1, 0.3, 1)) 0.5s;
}

.loader-content.is-active .loader-caption {
  opacity: 1;
  transform: translate3d(0, 0, 0);
}

.loader-percent {
  min-width: 3ch;
  text-align: left;
  color: var(--accent, #8b2500);
  font-variant-numeric: tabular-nums;
}

.loader-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(139, 37, 0, 0.25);
  border-top-color: var(--accent, #8b2500);
  border-radius: 50%;
  animation: loader-spin 0.8s linear infinite;
}

.loader-spinner.is-done {
  animation: none;
  border-color: var(--accent, #8b2500);
}

@keyframes loader-spin {
  to { transform: rotate(360deg); }
}

/* Exit Transition */
.journal-loader-leave-active {
  transition:
    opacity 0.42s var(--ease-quart, cubic-bezier(0.25, 1, 0.5, 1)),
    transform 0.5s var(--ease-expo, cubic-bezier(0.16, 1, 0.3, 1));
}

.journal-loader-leave-to {
  opacity: 0;
  transform: translate3d(0, -100%, 0);
}

@media (prefers-reduced-motion: reduce) {
  .loader-masthead,
  .loader-caption,
  .loader-ink-bar,
  .loader-ink-fill,
  .journal-loader-leave-active {
    transition-duration: 0.01s;
    transition-delay: 0s;
  }

  .loader-spinner {
    animation: none;
  }
}
</style>
