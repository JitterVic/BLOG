<script setup>
import { computed, onBeforeUnmount, ref } from "vue";

import { dispatchGoTopEvent } from "../constants/events";

const isJumping = ref(false);
const isWaving = ref(false);
const message = ref("回到顶部？");
const gazeX = ref(0);
const gazeY = ref(0);
let jumpTimer = 0;
let waveTimer = 0;

const JUMP_DURATION_MS = 980;
const REDUCED_MOTION_JUMP_DURATION_MS = 120;

const mascotStyle = computed(() => ({
  "--gaze-x": `${gazeX.value}px`,
  "--gaze-y": `${gazeY.value}px`,
}));

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function clearTimer(timerName) {
  if (timerName === "jump" && jumpTimer) {
    window.clearTimeout(jumpTimer);
    jumpTimer = 0;
  }
  if (timerName === "wave" && waveTimer) {
    window.clearTimeout(waveTimer);
    waveTimer = 0;
  }
}

function resetJump() {
  isJumping.value = false;
  message.value = "回到顶部？";
  jumpTimer = 0;
}

function startWave() {
  if (typeof window === "undefined") return;
  clearTimer("wave");
  isWaving.value = true;
  message.value = "嗨，要回顶部吗？";
  waveTimer = window.setTimeout(() => {
    isWaving.value = false;
    waveTimer = 0;
  }, prefersReducedMotion() ? 120 : 1200);
}

function stopWave() {
  clearTimer("wave");
  isWaving.value = false;
  gazeX.value = 0;
  gazeY.value = 0;
  if (!isJumping.value) message.value = "回到顶部？";
}

function followPointer(event) {
  if (prefersReducedMotion()) return;
  const rect = event.currentTarget.getBoundingClientRect();
  const offsetX = (event.clientX - (rect.left + rect.width / 2)) / (rect.width / 2);
  const offsetY = (event.clientY - (rect.top + rect.height * 0.4)) / (rect.height / 2);
  gazeX.value = Math.max(-1.8, Math.min(1.8, offsetX * 1.8));
  gazeY.value = Math.max(-1.2, Math.min(1.2, offsetY * 1.2));
}

function scrollToTop() {
  if (typeof window === "undefined") return;
  clearTimer("jump");
  clearTimer("wave");
  isJumping.value = true;
  isWaving.value = false;
  message.value = "冲呀！";
  dispatchGoTopEvent();
  const reducedMotion = prefersReducedMotion();
  window.scrollTo({ top: 0, behavior: reducedMotion ? "auto" : "smooth" });
  jumpTimer = window.setTimeout(
    resetJump,
    reducedMotion ? REDUCED_MOTION_JUMP_DURATION_MS : JUMP_DURATION_MS,
  );
}

onBeforeUnmount(() => {
  clearTimer("jump");
  clearTimer("wave");
});
</script>

<template>
  <button
    type="button"
    class="floating-cat"
    :class="{ 'is-jumping': isJumping, 'is-waving': isWaving }"
    :style="mascotStyle"
    aria-label="回到页面顶部"
    title="回到顶部"
    @click="scrollToTop"
    @pointerenter="startWave"
    @pointermove="followPointer"
    @pointerleave="stopWave"
    @focus="startWave"
    @blur="stopWave"
  >
    <span class="cat-speech" aria-hidden="true">{{ message }}</span>

    <span class="cat-figure" aria-hidden="true">
      <svg
        class="cat-svg"
        viewBox="0 0 120 132"
        width="120"
        height="132"
        xmlns="http://www.w3.org/2000/svg"
        focusable="false"
      >
        <defs>
          <linearGradient id="mascotFur" x1="24" y1="18" x2="94" y2="112" gradientUnits="userSpaceOnUse">
            <stop offset="0" stop-color="#fffdf4" />
            <stop offset="0.55" stop-color="#f6e6bd" />
            <stop offset="1" stop-color="#dfbd78" />
          </linearGradient>
          <linearGradient id="mascotBelly" x1="48" y1="73" x2="69" y2="112" gradientUnits="userSpaceOnUse">
            <stop offset="0" stop-color="#fffdf8" />
            <stop offset="1" stop-color="#f5dfb4" />
          </linearGradient>
          <linearGradient id="mascotScarf" x1="40" y1="63" x2="84" y2="96" gradientUnits="userSpaceOnUse">
            <stop offset="0" stop-color="#b84a2a" />
            <stop offset="1" stop-color="#7f210d" />
          </linearGradient>
          <radialGradient id="mascotEye" cx="38%" cy="32%" r="75%">
            <stop offset="0" stop-color="#d8a84f" />
            <stop offset="0.58" stop-color="#73501d" />
            <stop offset="1" stop-color="#23180e" />
          </radialGradient>
          <filter id="mascotShadow" x="-35%" y="-35%" width="170%" height="180%">
            <feDropShadow dx="0" dy="5" stdDeviation="3.2" flood-color="#3f2a16" flood-opacity="0.22" />
          </filter>
        </defs>

        <ellipse class="cat-ground" cx="60" cy="121" rx="30" ry="6" fill="rgba(55, 35, 18, 0.16)" />

        <g class="mascot-tail" filter="url(#mascotShadow)">
          <path d="M84 92c22 3 28-13 22-31-1 15-8 23-22 23" fill="none" stroke="#8a5a24" stroke-width="11" stroke-linecap="round" />
          <path d="M84 92c22 3 28-13 22-31" fill="none" stroke="#efd493" stroke-width="6.2" stroke-linecap="round" />
          <path d="M102 72c3-4 4-8 4-12" fill="none" stroke="#b98942" stroke-width="3" stroke-linecap="round" opacity="0.72" />
        </g>

        <g class="mascot-body" filter="url(#mascotShadow)">
          <path d="M32 72c-4 22 6 43 28 46 22-3 32-24 28-46-2-15-12-24-28-24S34 57 32 72Z" fill="url(#mascotFur)" stroke="#74471b" stroke-width="2.8" />
          <ellipse cx="60" cy="91" rx="15" ry="20" fill="url(#mascotBelly)" opacity="0.92" />
          <path d="M39 67c11 7 30 8 43 0l-2 13c-12 7-28 6-39 0Z" fill="url(#mascotScarf)" stroke="#69200f" stroke-width="2" />
          <path class="mascot-scarf-tail" d="M76 77c10 4 13 12 11 23l-8-5-6 7c2-10-1-17-5-22Z" fill="#9d3219" stroke="#69200f" stroke-width="2" stroke-linejoin="round" />
        </g>

        <g class="mascot-head">
          <g class="mascot-ear mascot-ear--left">
            <path d="M37 37 25 13l25 11Z" fill="url(#mascotFur)" stroke="#74471b" stroke-width="2.8" stroke-linejoin="round" />
            <path d="m35 30-6-11 13 6Z" fill="#efaa9d" opacity="0.85" />
          </g>
          <g class="mascot-ear mascot-ear--right">
            <path d="m83 37 12-24-25 11Z" fill="url(#mascotFur)" stroke="#74471b" stroke-width="2.8" stroke-linejoin="round" />
            <path d="m85 30 6-11-13 6Z" fill="#efaa9d" opacity="0.85" />
          </g>

          <path d="M31 41c1-18 13-27 29-27s28 9 29 27c2 20-10 34-29 34S29 61 31 41Z" fill="url(#mascotFur)" stroke="#74471b" stroke-width="2.8" filter="url(#mascotShadow)" />
          <path d="M46 19c6-3 22-3 28 0" fill="none" stroke="#c18a45" stroke-width="3" stroke-linecap="round" opacity="0.7" />
          <path d="m52 18-3 8m11-10v10m8-8 3 8" fill="none" stroke="#b67e39" stroke-width="2.4" stroke-linecap="round" opacity="0.72" />

          <g class="mascot-eyes">
            <ellipse cx="46" cy="43" rx="7.2" ry="8.6" fill="#fffdf7" stroke="#5d3a18" stroke-width="1.8" />
            <ellipse cx="74" cy="43" rx="7.2" ry="8.6" fill="#fffdf7" stroke="#5d3a18" stroke-width="1.8" />
            <g class="mascot-pupils">
              <ellipse cx="46" cy="44" rx="4.5" ry="5.8" fill="url(#mascotEye)" />
              <ellipse cx="74" cy="44" rx="4.5" ry="5.8" fill="url(#mascotEye)" />
              <circle cx="44.6" cy="41.8" r="1.45" fill="#fff" />
              <circle cx="72.6" cy="41.8" r="1.45" fill="#fff" />
            </g>
          </g>

          <ellipse class="cat-blush-svg" cx="39" cy="54" rx="6" ry="3" fill="#e98f82" opacity="0.58" />
          <ellipse class="cat-blush-svg" cx="81" cy="54" rx="6" ry="3" fill="#e98f82" opacity="0.58" />
          <path d="M60 50c2.2 0 4 1.3 4 2.5 0 1.4-1.8 2.6-4 2.6s-4-1.2-4-2.6c0-1.2 1.8-2.5 4-2.5Z" fill="#d47468" />
          <path d="M60 55v3.5m0 0c-3 2.8-6.5 2.3-8 .7m8-.7c3 2.8 6.5 2.3 8 .7" fill="none" stroke="#74471b" stroke-width="1.6" stroke-linecap="round" />
          <g stroke="#7f5425" stroke-width="1.25" stroke-linecap="round" opacity="0.76">
            <path d="M28 52h15m-16 5 16-2m49-3H77m16 5-16-2" />
          </g>
        </g>

        <g class="mascot-paws">
          <g class="mascot-paw mascot-paw--left">
            <path d="M37 85c-7 6-8 18-2 23 5 4 12 0 12-7V87" fill="url(#mascotFur)" stroke="#74471b" stroke-width="2.6" stroke-linecap="round" />
            <path d="m36 101 4 1m-1-5 4 1" stroke="#c18a78" stroke-width="1.4" stroke-linecap="round" />
          </g>
          <g class="mascot-paw mascot-paw--right">
            <path d="M83 85c7 6 8 18 2 23-5 4-12 0-12-7V87" fill="url(#mascotFur)" stroke="#74471b" stroke-width="2.6" stroke-linecap="round" />
            <path d="m84 101-4 1m1-5-4 1" stroke="#c18a78" stroke-width="1.4" stroke-linecap="round" />
          </g>
          <ellipse cx="45" cy="115" rx="11" ry="6" fill="url(#mascotFur)" stroke="#74471b" stroke-width="2.4" />
          <ellipse cx="75" cy="115" rx="11" ry="6" fill="url(#mascotFur)" stroke="#74471b" stroke-width="2.4" />
        </g>

        <g class="mascot-sparkles" fill="#b84a2a">
          <path d="m18 42 1.8 4.2L24 48l-4.2 1.8L18 54l-1.8-4.2L12 48l4.2-1.8Z" />
          <path d="m101 31 1.2 2.8 2.8 1.2-2.8 1.2-1.2 2.8-1.2-2.8L97 35l2.8-1.2Z" />
        </g>
      </svg>
    </span>
    <span class="cat-caption">TOP</span>
  </button>
</template>
