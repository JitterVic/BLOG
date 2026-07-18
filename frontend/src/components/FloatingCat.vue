<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const isVisible = ref(false);
const isJumping = ref(false);
const isWaving = ref(false);
const isComplete = ref(false);
let scrollFrame = 0;
let jumpTimer = 0;
let waveTimer = 0;
let completeTimer = 0;
let completionShownForPath = "";
let runtimeEnabled = false;
let motionQuery = null;
let coarsePointerQuery = null;

const SHOW_AFTER_PX = 500;
const COMPLETE_THRESHOLD = 0.94;

const routeMessage = computed(() => {
  if (isJumping.value) return "回到开头！";
  if (isComplete.value) return "读完啦，辛苦了";
  if (route.name === "post") return "慢慢读，别着急";
  if (route.name === "posts") return "挑一篇慢慢看";
  if (route.name === "about") return "欢迎来到编辑部";
  return "今天想读点什么？";
});

const accessoryClass = computed(() => ({
  "is-reading": route.name === "post",
  "is-catalog": route.name === "posts",
  "is-about": route.name === "about",
}));

function clearTimer(timer) {
  if (timer) window.clearTimeout(timer);
}

function shouldRunRuntime() {
  // Keep scroll/top-button usable on touch devices; only pause while the tab is hidden.
  return document.visibilityState === "visible";
}

function prefersReducedMotion() {
  return motionQuery?.matches
    ?? window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
    ?? false;
}

function prefersReducedEffects() {
  return prefersReducedMotion()
    || (coarsePointerQuery?.matches
      ?? window.matchMedia?.("(pointer: coarse)")?.matches
      ?? false)
    || Number(navigator.maxTouchPoints || 0) > 0;
}

const reducedFx = ref(false);

function refreshReducedFx() {
  reducedFx.value = prefersReducedEffects();
}

function updateScrollState() {
  if (!runtimeEnabled) return;
  const y = window.scrollY || 0;
  const doc = document.documentElement;
  const maxScroll = Math.max(doc.scrollHeight - window.innerHeight, 1);
  const progress = y / maxScroll;
  isVisible.value = y >= SHOW_AFTER_PX;

  if (
    route.name === "post"
    && progress >= COMPLETE_THRESHOLD
    && completionShownForPath !== route.fullPath
  ) {
    completionShownForPath = route.fullPath;
    isComplete.value = true;
    clearTimer(completeTimer);
    completeTimer = window.setTimeout(() => {
      isComplete.value = false;
      completeTimer = 0;
    }, 1800);
  }
}

function scheduleScrollUpdate() {
  if (!runtimeEnabled || scrollFrame) return;
  scrollFrame = window.requestAnimationFrame(() => {
    scrollFrame = 0;
    updateScrollState();
  });
}

function startWave() {
  clearTimer(waveTimer);
  isWaving.value = true;
  waveTimer = window.setTimeout(() => {
    isWaving.value = false;
    waveTimer = 0;
  }, 760);
}

function stopWave() {
  clearTimer(waveTimer);
  isWaving.value = false;
  waveTimer = 0;
}

function scrollToTop() {
  clearTimer(jumpTimer);
  isJumping.value = true;
  window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  jumpTimer = window.setTimeout(() => {
    isJumping.value = false;
    jumpTimer = 0;
  }, prefersReducedMotion() ? 0 : 720);
}

watch(
  () => route.fullPath,
  () => {
    if (!runtimeEnabled) return;
    completionShownForPath = "";
    isComplete.value = false;
    window.requestAnimationFrame(updateScrollState);
  },
);

function setRuntimeEnabled(enabled) {
  if (enabled === runtimeEnabled) return;
  runtimeEnabled = enabled;

  if (!enabled) {
    window.removeEventListener("scroll", scheduleScrollUpdate);
    window.removeEventListener("resize", scheduleScrollUpdate);
    if (scrollFrame) window.cancelAnimationFrame(scrollFrame);
    scrollFrame = 0;
    isVisible.value = false;
    isComplete.value = false;
    clearTimer(completeTimer);
    completeTimer = 0;
    return;
  }

  updateScrollState();
  window.addEventListener("scroll", scheduleScrollUpdate, { passive: true });
  window.addEventListener("resize", scheduleScrollUpdate, { passive: true });
}

function refreshRuntimeAvailability() {
  setRuntimeEnabled(shouldRunRuntime());
}

function handleVisibilityChange() {
  refreshRuntimeAvailability();
}

function handlePreferenceChange() {
  refreshRuntimeAvailability();
  refreshReducedFx();
}

onMounted(() => {
  motionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)") || null;
  coarsePointerQuery = window.matchMedia?.("(pointer: coarse)") || null;
  motionQuery?.addEventListener?.("change", handlePreferenceChange);
  coarsePointerQuery?.addEventListener?.("change", handlePreferenceChange);
  document.addEventListener("visibilitychange", handleVisibilityChange, { passive: true });
  refreshReducedFx();
  refreshRuntimeAvailability();
});

onBeforeUnmount(() => {
  setRuntimeEnabled(false);
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  motionQuery?.removeEventListener?.("change", handlePreferenceChange);
  coarsePointerQuery?.removeEventListener?.("change", handlePreferenceChange);
  clearTimer(jumpTimer);
  clearTimer(waveTimer);
  clearTimer(completeTimer);
});
</script>

<template>
  <button
    type="button"
    class="floating-cat editor-cat"
    :class="[
      accessoryClass,
      {
        'is-visible': isVisible,
        'is-jumping': isJumping,
        'is-waving': isWaving,
        'is-complete': isComplete,
        'is-reduced-fx': reducedFx,
      },
    ]"
    :aria-hidden="!isVisible"
    :tabindex="isVisible ? 0 : -1"
    aria-label="回到页面顶部"
    title="回到顶部"
    @click="scrollToTop"
    @pointerenter="startWave"
    @pointerleave="stopWave"
    @focus="startWave"
    @blur="stopWave"
  >
    <span class="editor-cat__speech" aria-hidden="true">{{ routeMessage }}</span>

    <span class="cat-figure editor-cat__figure" aria-hidden="true">
      <svg
        class="cat-svg editor-cat__svg"
        viewBox="0 0 120 132"
        xmlns="http://www.w3.org/2000/svg"
        focusable="false"
      >
        <g class="editor-cat__tail" fill="none" stroke-linecap="round">
          <path d="M83 93c21 4 29-10 23-28-1 14-8 22-21 22" stroke="#6d4b28" stroke-width="9" />
          <path d="M83 93c21 4 29-10 23-28" stroke="#f0dfb5" stroke-width="5" />
        </g>

        <path
          class="editor-cat__body"
          d="M34 72c-4 20 5 41 26 44 21-3 30-24 26-44-2-14-11-22-26-22S36 58 34 72Z"
          fill="#f6e8c8"
          stroke="#4b3827"
          stroke-width="2.6"
        />
        <path d="M41 68c10 7 28 8 39 0l-2 12c-11 6-25 6-35 0Z" fill="#9b321d" stroke="#5f2418" stroke-width="2" />
        <path class="editor-cat__scarf" d="M76 77c9 3 12 11 10 21l-7-4-6 7c2-10-1-16-5-20Z" fill="#b7472d" stroke="#5f2418" stroke-width="2" />

        <g class="editor-cat__head">
          <path d="M37 37 26 15l23 10Z" fill="#f6e8c8" stroke="#4b3827" stroke-width="2.6" stroke-linejoin="round" />
          <path d="m83 37 11-22-23 10Z" fill="#f6e8c8" stroke="#4b3827" stroke-width="2.6" stroke-linejoin="round" />
          <path d="m36 30-5-9 11 5Z" fill="#d99487" opacity="0.7" />
          <path d="m84 30 5-9-11 5Z" fill="#d99487" opacity="0.7" />
          <path d="M31 42c0-18 12-27 29-27s29 9 29 27c1 19-11 32-29 32S30 61 31 42Z" fill="#f8edcf" stroke="#4b3827" stroke-width="2.6" />

          <g class="editor-cat__eyes">
            <ellipse cx="46" cy="44" rx="4.7" ry="3.8" fill="#fff7dd" stroke="#3e3024" stroke-width="1.7" />
            <ellipse cx="74" cy="44" rx="4.7" ry="3.8" fill="#fff7dd" stroke="#3e3024" stroke-width="1.7" />
            <circle cx="46" cy="44.3" r="1.9" fill="#3e3024" />
            <circle cx="74" cy="44.3" r="1.9" fill="#3e3024" />
            <circle cx="44.7" cy="43.1" r="0.55" fill="#fffdf3" />
            <circle cx="72.7" cy="43.1" r="0.55" fill="#fffdf3" />
          </g>
          <g v-if="route.name === 'post'" class="editor-cat__glasses" fill="none" stroke="#7c2f1c" stroke-width="1.5">
            <circle cx="46" cy="43" r="7" />
            <circle cx="74" cy="43" r="7" />
            <path d="M53 43h14M39 41l-6-2m48 2 6-2" />
          </g>

          <path d="M60 50c2 0 3.5 1.2 3.5 2.2 0 1.2-1.5 2.2-3.5 2.2s-3.5-1-3.5-2.2C56.5 51.2 58 50 60 50Z" fill="#b95e54" />
          <path d="M60 54.5v3m0 0c-2.7 2.4-5.5 2-7 .6m7-.6c2.7 2.4 5.5 2 7 .6" fill="none" stroke="#4b3827" stroke-width="1.5" stroke-linecap="round" />
          <path d="M29 52h14m-15 5 15-2m48-3H77m15 5-15-2" fill="none" stroke="#6d4b28" stroke-width="1.1" stroke-linecap="round" opacity="0.7" />
        </g>

        <g class="editor-cat__paws" fill="#f6e8c8" stroke="#4b3827" stroke-width="2.4" stroke-linecap="round">
          <path d="M40 84c-6 6-7 17-2 21 5 4 10 0 10-6V87" />
          <path class="editor-cat__wave-paw" d="M80 84c6 6 7 17 2 21-5 4-10 0-10-6V87" />
        </g>

        <g class="editor-cat__pencil" transform="translate(44 90) rotate(-18)">
          <rect x="0" y="0" width="29" height="5" rx="2.5" fill="#c78934" stroke="#5c4026" stroke-width="1.3" />
          <path d="m29 0 8 2.5-8 2.5Z" fill="#ead7aa" stroke="#5c4026" stroke-width="1.3" stroke-linejoin="round" />
          <path d="m36 2 2 0.5-2 0.5Z" fill="#33271e" />
          <rect x="2" y="0" width="4" height="5" fill="#a83d2a" />
        </g>

        <path v-if="route.name === 'posts'" class="editor-cat__paper" d="M24 77h18v23H24Z" fill="#fffaf0" stroke="#4b3827" stroke-width="1.6" />
        <path v-if="route.name === 'posts'" d="M28 83h10m-10 5h10m-10 5h7" stroke="#9b321d" stroke-width="1.2" />

        <g v-if="isComplete" class="editor-cat__complete" fill="#9b321d">
          <path d="m18 42 2 4.5 4.5 2-4.5 2-2 4.5-2-4.5-4.5-2 4.5-2Z" />
          <path d="m101 31 1.4 3.2 3.2 1.4-3.2 1.4-1.4 3.2-1.4-3.2-3.2-1.4 3.2-1.4Z" />
        </g>
      </svg>
    </span>
    <span class="cat-caption editor-cat__caption">TOP</span>
  </button>
</template>
