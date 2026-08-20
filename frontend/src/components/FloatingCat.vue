<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const catEl = ref(null);
const isVisible = ref(false);
const isJumping = ref(false);
const isWaving = ref(false);
const isComplete = ref(false);
const hasBubble = ref(false);
const petCount = ref(0);
const particles = ref([]);
const scrollProgress = ref(0);

// Eye tracking offsets in SVG units
const eyeOffsetX = ref(0);
const eyeOffsetY = ref(0);

let scrollFrame = 0;
let jumpTimer = 0;
let waveTimer = 0;
let completeTimer = 0;
let bubbleTimer = 0;
let particleId = 0;
let completionShownForPath = "";
let runtimeEnabled = false;
let motionQuery = null;
let coarsePointerQuery = null;
let eyeTrackingRaf = 0;
let targetEyeX = 0;
let targetEyeY = 0;

const SHOW_AFTER_PX = 400;
const COMPLETE_THRESHOLD = 0.94;
const RING_CIRCUMFERENCE = 258; // 2 * PI * 41

// Dynamic Contextual Dialogue
const contextualMessage = computed(() => {
  if (isJumping.value) return "嗖—— 飞回顶部啦！🚀";
  if (isComplete.value) return "读完啦！给作者点个赞吧 ✨";

  // Petting response
  if (petCount.value >= 5) return "呼噜呼噜~ 最喜欢你啦 🐾";
  if (petCount.value >= 3) return "喵呜~ 摸摸头，代码没 bug！";
  if (petCount.value >= 1) return "按我一键火箭飞回顶部哦 🚀";

  const hour = new Date().getHours();
  const isNight = hour >= 23 || hour < 6;
  const isMorning = hour >= 6 && hour < 11;

  if (route.name === "post") {
    if (isNight) return "夜深了，注意护眼哦 🌙";
    if (scrollProgress.value > 0.6) return "读得好快，思路顺畅吗？📖";
    return "戴上眼镜，慢慢品读 👓";
  }

  if (route.name === "posts") {
    if (scrollProgress.value > 0.5) return "翻到以前的归档啦 📜";
    return "挑一篇喜欢的细细看 ☕";
  }

  if (route.name === "about") {
    return "欢迎来到至知编辑部 🍵";
  }

  if (isMorning) return "早安！今天想探索点什么？☀️";
  if (isNight) return "夜深了，来杯热茶歇歇吧 🍵";
  return "今天也一起探索新知吧 🐾";
});

const progressOffset = computed(() => {
  const p = Math.min(Math.max(scrollProgress.value, 0), 1);
  return RING_CIRCUMFERENCE * (1 - p);
});

// Cat remains mounted and visible during jump animation even if scrollY < SHOW_AFTER_PX
const shouldBeVisible = computed(() => isVisible.value || isJumping.value);

const accessoryClass = computed(() => ({
  "is-reading": route.name === "post",
  "is-catalog": route.name === "posts",
  "is-about": route.name === "about",
}));

function clearTimer(timer) {
  if (timer) window.clearTimeout(timer);
}

function shouldRunRuntime() {
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
  const progress = Math.min(Math.max(y / maxScroll, 0), 1);
  scrollProgress.value = progress;
  isVisible.value = y >= SHOW_AFTER_PX;

  if (
    route.name === "post"
    && progress >= COMPLETE_THRESHOLD
    && completionShownForPath !== route.fullPath
  ) {
    completionShownForPath = route.fullPath;
    isComplete.value = true;
    spawnParticles("✨", 4);
    clearTimer(completeTimer);
    completeTimer = window.setTimeout(() => {
      isComplete.value = false;
      completeTimer = 0;
    }, 2400);
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
  hasBubble.value = true;
  clearTimer(bubbleTimer);
  bubbleTimer = window.setTimeout(() => {
    hasBubble.value = false;
  }, 3400);
  waveTimer = window.setTimeout(() => {
    isWaving.value = false;
    waveTimer = 0;
  }, 900);
}

function stopWave() {
  clearTimer(waveTimer);
  isWaving.value = false;
  waveTimer = 0;
}

function spawnParticles(symbol = "❤️", count = 2) {
  if (reducedFx.value) return;
  for (let i = 0; i < count; i++) {
    const id = ++particleId;
    const drift = (Math.random() * 32 - 16).toFixed(1);
    particles.value.push({ id, symbol, drift });
    window.setTimeout(() => {
      particles.value = particles.value.filter((p) => p.id !== id);
    }, 1100);
  }
}

function handleCatClick() {
  petCount.value += 1;
  spawnParticles(petCount.value % 2 === 0 ? "🐾" : "❤️", 2);
  scrollToTop();
}

function scrollToTop() {
  clearTimer(jumpTimer);
  isJumping.value = true;
  hasBubble.value = true;
  spawnParticles("✨", 4);

  window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  
  jumpTimer = window.setTimeout(() => {
    isJumping.value = false;
    jumpTimer = 0;
    petCount.value = 0;
    hasBubble.value = false;
    updateScrollState();
  }, prefersReducedMotion() ? 0 : 1150);
}

// Robust Mouse Eye Tracking directly on SVG coordinate space
function handlePointerMove(e) {
  if (reducedFx.value || !catEl.value) return;
  const rect = catEl.value.getBoundingClientRect();
  const faceX = rect.left + rect.width * 0.5;
  const faceY = rect.top + rect.height * 0.36;

  const dx = e.clientX - faceX;
  const dy = e.clientY - faceY;
  const dist = Math.hypot(dx, dy) || 1;
  const maxRange = 3.6; // SVG coordinate range
  const intensity = Math.min(dist / 320, 1);

  targetEyeX = (dx / dist) * maxRange * intensity;
  targetEyeY = (dy / dist) * maxRange * intensity;

  if (!eyeTrackingRaf) {
    eyeTrackingRaf = window.requestAnimationFrame(updateEyeTracking);
  }
}

function updateEyeTracking() {
  eyeTrackingRaf = 0;
  eyeOffsetX.value += (targetEyeX - eyeOffsetX.value) * 0.32;
  eyeOffsetY.value += (targetEyeY - eyeOffsetY.value) * 0.32;

  if (
    Math.abs(targetEyeX - eyeOffsetX.value) > 0.04 ||
    Math.abs(targetEyeY - eyeOffsetY.value) > 0.04
  ) {
    eyeTrackingRaf = window.requestAnimationFrame(updateEyeTracking);
  }
}

watch(
  () => route.fullPath,
  () => {
    if (!runtimeEnabled) return;
    completionShownForPath = "";
    isComplete.value = false;
    petCount.value = 0;
    window.requestAnimationFrame(updateScrollState);
  },
);

function setRuntimeEnabled(enabled) {
  if (enabled === runtimeEnabled) return;
  runtimeEnabled = enabled;

  if (!enabled) {
    window.removeEventListener("scroll", scheduleScrollUpdate);
    window.removeEventListener("resize", scheduleScrollUpdate);
    window.removeEventListener("pointermove", handlePointerMove);
    if (scrollFrame) window.cancelAnimationFrame(scrollFrame);
    if (eyeTrackingRaf) window.cancelAnimationFrame(eyeTrackingRaf);
    scrollFrame = 0;
    eyeTrackingRaf = 0;
    isVisible.value = false;
    isComplete.value = false;
    clearTimer(completeTimer);
    completeTimer = 0;
    return;
  }

  updateScrollState();
  window.addEventListener("scroll", scheduleScrollUpdate, { passive: true });
  window.addEventListener("resize", scheduleScrollUpdate, { passive: true });
  window.addEventListener("pointermove", handlePointerMove, { passive: true });
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
  clearTimer(bubbleTimer);
});
</script>

<template>
  <button
    ref="catEl"
    type="button"
    class="floating-cat editor-cat"
    :class="[
      accessoryClass,
      {
        'is-visible': shouldBeVisible,
        'is-jumping': isJumping,
        'is-waving': isWaving,
        'is-complete': isComplete,
        'has-bubble': hasBubble,
        'is-reduced-fx': reducedFx,
      },
    ]"
    :aria-hidden="!shouldBeVisible"
    :tabindex="shouldBeVisible ? 0 : -1"
    aria-label="回到页面顶部"
    title="回到顶部 (摸摸我)"
    @click="handleCatClick"
    @pointerenter="startWave"
    @pointerleave="stopWave"
    @focus="startWave"
    @blur="stopWave"
  >
    <!-- Dynamic Speech Bubble -->
    <span class="editor-cat__speech" aria-hidden="true">{{ contextualMessage }}</span>

    <!-- Reading Progress Circular Halo Ring -->
    <svg class="editor-cat__ring-svg" viewBox="0 0 92 92" aria-hidden="true">
      <circle cx="46" cy="46" r="41" class="cat-ring-track" />
      <circle
        cx="46"
        cy="46"
        r="41"
        class="cat-ring-fill"
        :style="{ strokeDashoffset: `${progressOffset}px` }"
      />
    </svg>

    <!-- Interactive Heart/Paw/Sparkle Floating Particles -->
    <div class="editor-cat__particles" aria-hidden="true">
      <span
        v-for="p in particles"
        :key="p.id"
        class="cat-bubble-particle"
        :style="{ '--p-drift': `${p.drift}px` }"
      >
        {{ p.symbol }}
      </span>
    </div>

    <!-- Main Cat SVG Visual System -->
    <span class="cat-figure editor-cat__figure" aria-hidden="true">
      <svg
        class="cat-svg editor-cat__svg"
        viewBox="0 0 120 136"
        xmlns="http://www.w3.org/2000/svg"
        focusable="false"
      >
        <defs>
          <radialGradient id="catCoatGrad" cx="45%" cy="40%" r="55%">
            <stop offset="0%" stop-color="#fffdf6" />
            <stop offset="65%" stop-color="#f8edcf" />
            <stop offset="100%" stop-color="#eed8a6" />
          </radialGradient>
          <linearGradient id="catScarfGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="#bd3f24" />
            <stop offset="100%" stop-color="#8b2500" />
          </linearGradient>
          <radialGradient id="catBellGrad" cx="35%" cy="30%" r="60%">
            <stop offset="0%" stop-color="#fff2a8" />
            <stop offset="50%" stop-color="#e8ad38" />
            <stop offset="100%" stop-color="#aa6f15" />
          </radialGradient>
        </defs>

        <!-- Ambient Ground Shadow -->
        <ellipse
          class="editor-cat__shadow"
          cx="60"
          cy="124"
          rx="34"
          ry="7"
          fill="#332416"
        />

        <!-- Swaying Tail -->
        <g class="editor-cat__tail" fill="none" stroke-linecap="round">
          <path d="M84 94c22 4 30-10 24-28-1 14-8 22-22 22" stroke="#5d4329" stroke-width="8.5" />
          <path d="M84 94c22 4 30-10 24-28" stroke="url(#catCoatGrad)" stroke-width="5" />
          <circle cx="107" cy="67" r="2.8" fill="#d99487" />
        </g>

        <!-- Cat Body -->
        <path
          class="editor-cat__body"
          d="M34 72c-4 20 5 41 26 44 21-3 30-24 26-44-2-14-11-22-26-22S36 58 34 72Z"
          fill="url(#catCoatGrad)"
          stroke="#443222"
          stroke-width="2.6"
          stroke-linejoin="round"
        />

        <!-- Warm Red Scarf & Golden Bell -->
        <path d="M41 68c10 7 28 8 39 0l-2 12c-11 6-25 6-35 0Z" fill="url(#catScarfGrad)" stroke="#531c12" stroke-width="2" />
        <path class="editor-cat__scarf" d="M75 76c9 3 13 11 11 21l-7-4-6 7c2-10-1-16-5-20Z" fill="url(#catScarfGrad)" stroke="#531c12" stroke-width="2" />
        
        <g class="editor-cat__bell" transform="translate(56 78)">
          <circle cx="4" cy="4" r="4.2" fill="url(#catBellGrad)" stroke="#684209" stroke-width="1.2" />
          <line x1="1" y1="4" x2="7" y2="4" stroke="#684209" stroke-width="0.9" />
          <circle cx="4" cy="5.8" r="0.9" fill="#3a2408" />
        </g>

        <!-- Head, Ears, Face -->
        <g class="editor-cat__head">
          <!-- Ears with inner tufts -->
          <g class="editor-cat__ears">
            <path d="M37 37 25 14l24 11Z" fill="url(#catCoatGrad)" stroke="#443222" stroke-width="2.6" stroke-linejoin="round" />
            <path d="m83 37 12-23-24 11Z" fill="url(#catCoatGrad)" stroke="#443222" stroke-width="2.6" stroke-linejoin="round" />
            <path d="m36 30-6-10 12 6Z" fill="#e59e92" opacity="0.85" />
            <path d="m84 30 6-10-12 6Z" fill="#e59e92" opacity="0.85" />
            <path d="m33 27 4 3-2-6Z" fill="#ffffff" opacity="0.9" />
            <path d="m87 27-4 3 2-6Z" fill="#ffffff" opacity="0.9" />
          </g>

          <!-- Head Base Oval -->
          <path d="M30 42c0-19 13-28 30-28s30 9 30 28c1 20-12 33-30 33S29 62 30 42Z" fill="url(#catCoatGrad)" stroke="#443222" stroke-width="2.6" />

          <!-- Blush Cheeks -->
          <ellipse cx="37" cy="52" rx="4.5" ry="2.8" fill="#f0aba0" opacity="0.55" />
          <ellipse cx="83" cy="52" rx="4.5" ry="2.8" fill="#f0aba0" opacity="0.55" />

          <!-- Expressive Eyes with Eye-Tracking Pupils -->
          <g class="editor-cat__eyes">
            <!-- Sclera -->
            <ellipse cx="46" cy="44" rx="5.2" ry="4.2" fill="#fffcf0" stroke="#3e3024" stroke-width="1.8" />
            <ellipse cx="74" cy="44" rx="5.2" ry="4.2" fill="#fffcf0" stroke="#3e3024" stroke-width="1.8" />
            
            <!-- Pupil (Reactive eye-tracking via direct :cx and :cy) -->
            <g class="editor-cat__pupil-group">
              <circle :cx="46 + eyeOffsetX" :cy="44.2 + eyeOffsetY" r="2.6" fill="#322419" />
              <circle :cx="74 + eyeOffsetX" :cy="44.2 + eyeOffsetY" r="2.6" fill="#322419" />
              <!-- Dual Catchlight Sparkles -->
              <circle :cx="44.8 + eyeOffsetX * 0.7" :cy="42.8 + eyeOffsetY * 0.7" r="0.9" fill="#ffffff" />
              <circle :cx="72.8 + eyeOffsetX * 0.7" :cy="42.8 + eyeOffsetY * 0.7" r="0.9" fill="#ffffff" />
              <circle :cx="47.2 + eyeOffsetX * 0.7" :cy="45.3 + eyeOffsetY * 0.7" r="0.45" fill="#ffffff" />
              <circle :cx="75.2 + eyeOffsetX * 0.7" :cy="45.3 + eyeOffsetY * 0.7" r="0.45" fill="#ffffff" />
            </g>
          </g>

          <!-- Reading Glasses (Post view accessory) -->
          <g v-if="route.name === 'post'" class="editor-cat__glasses" fill="none" stroke="#7a2b18" stroke-width="1.6">
            <circle cx="46" cy="43.5" r="7.5" fill="rgba(255, 255, 255, 0.15)" />
            <circle cx="74" cy="43.5" r="7.5" fill="rgba(255, 255, 255, 0.15)" />
            <path d="M53.5 43.5h7M38.5 41.5l-6-2.5m49 2.5 6-2.5" />
          </g>

          <!-- Cute Pink Nose & Mouth -->
          <path d="M60 49.5c2.2 0 3.8 1.4 3.8 2.5 0 1.3-1.6 2.4-3.8 2.4s-3.8-1.1-3.8-2.4c0-1.1 1.6-2.5 3.8-2.5Z" fill="#bd6157" />
          <path d="M60 54.4v3.2m0 0c-2.8 2.5-5.8 2.1-7.4.7m7.4-.7c2.8 2.5 5.8 2.1 7.4.7" fill="none" stroke="#443222" stroke-width="1.6" stroke-linecap="round" />
          
          <!-- Whiskers -->
          <path d="M26 51h15m-16 5.5 16-2.5m47-3H79m16 5.5-16-2.5" fill="none" stroke="#5d4329" stroke-width="1.2" stroke-linecap="round" opacity="0.75" />
        </g>

        <!-- Cute Paws -->
        <g class="editor-cat__paws" fill="url(#catCoatGrad)" stroke="#443222" stroke-width="2.5" stroke-linecap="round">
          <path d="M39 84c-6 6-7 17-2 21 5 4 10 0 10-6V87" />
          <!-- Waving Paw on Hover -->
          <path class="editor-cat__wave-paw" d="M81 84c6 6 7 17 2 21-5 4-10 0-10-6V87" />
        </g>

        <!-- Pencil / Quill Accessory -->
        <g class="editor-cat__pencil" transform="translate(43 89) rotate(-18)">
          <rect x="0" y="0" width="30" height="5.2" rx="2.6" fill="#c78934" stroke="#523922" stroke-width="1.3" />
          <path d="m30 0 9 2.6-9 2.6Z" fill="#ead7aa" stroke="#523922" stroke-width="1.3" stroke-linejoin="round" />
          <path d="m37 2.1 2 0.5-2 0.5Z" fill="#291e17" />
          <rect x="2" y="0" width="4.5" height="5.2" fill="#9b321d" />
        </g>

        <!-- Reading Catalog Scroll (Posts view accessory) -->
        <g v-if="route.name === 'posts'" class="editor-cat__paper">
          <path d="M22 75h20v24H22Z" fill="#fffdf6" stroke="#443222" stroke-width="1.6" />
          <path d="M26 81h12m-12 5h12m-12 5h8" stroke="#9b321d" stroke-width="1.2" stroke-linecap="round" />
        </g>

        <!-- Article Finish Celebration Stars -->
        <g v-if="isComplete" class="editor-cat__complete" fill="#d95e34">
          <path d="m16 40 2.2 5 5 2.2-5 2.2-2.2 5-2.2-5-5-2.2 5-2.2Z" />
          <path d="m103 29 1.6 3.6 3.6 1.6-3.6 1.6-1.6 3.6-1.6-3.6-3.6-1.6 3.6-1.6Z" />
        </g>
      </svg>
    </span>

    <span class="cat-caption editor-cat__caption">TOP</span>
  </button>
</template>
