<script setup>
import { computed, onMounted, ref } from "vue";
import { useCatPet } from "../../composables/useCatPet";
import CatAvatar from "./CatAvatar.vue";
import CatBubble from "./CatBubble.vue";

const widgetRef = ref(null);

const {
  petState,
  isHovered,
  isDragging,
  isSoundOn,
  scrollProgress,
  scrollY,
  isVisible,
  gazeX,
  gazeY,
  bubbleVisible,
  bubbleText,
  bubbleTag,
  petPosition,
  hasCustomPosition,
  currentRouteName,
  statusText,
  showBubble,
  hideBubble,
  handlePetClick,
  triggerRandomAction,
  launchToTop,
  toggleSound,
  savePosition,
  resetPosition,
} = useCatPet();

// 环形阅读进度条周长
const RING_CIRCUMFERENCE = 282; // 2 * PI * 45
const progressOffset = computed(() => {
  const p = Math.min(Math.max(scrollProgress.value, 0), 1);
  return RING_CIRCUMFERENCE * (1 - p);
});

// 拖拽手势状态
let startPointerX = 0;
let startPointerY = 0;
let initialPetX = 0;
let initialPetY = 0;
let hasMoved = false;
let clickTimeout = null;

function handlePointerDown(e) {
  // 只响应主按键
  if (e.button !== 0 && e.pointerType === "mouse") return;

  const target = e.target;
  // 如果点击的是气泡内的按钮，不触发拖拽
  if (target.closest(".cat-speech-bubble")) return;

  startPointerX = e.clientX;
  startPointerY = e.clientY;
  initialPetX = petPosition.value.x;
  initialPetY = petPosition.value.y;
  hasMoved = false;

  window.addEventListener("pointermove", handlePointerMoveWindow);
  window.addEventListener("pointerup", handlePointerUpWindow);
}

function handlePointerMoveWindow(e) {
  const dx = e.clientX - startPointerX;
  const dy = e.clientY - startPointerY;

  if (!hasMoved && Math.hypot(dx, dy) > 6) {
    hasMoved = true;
    isDragging.value = true;
    hideBubble();
  }

  if (hasMoved) {
    // 限制拖拽范围在视口内
    const petW = 100;
    const petH = 100;
    const maxLeftOffset = -(window.innerWidth - petW - 20);
    const maxTopOffset = -(window.innerHeight - petH - 20);

    const nextX = Math.min(20, Math.max(maxLeftOffset, initialPetX + dx));
    const nextY = Math.min(20, Math.max(maxTopOffset, initialPetY + dy));

    petPosition.value = { x: nextX, y: nextY };
  }
}

function handlePointerUpWindow() {
  window.removeEventListener("pointermove", handlePointerMoveWindow);
  window.removeEventListener("pointerup", handlePointerUpWindow);

  if (hasMoved) {
    isDragging.value = false;
    savePosition(petPosition.value.x, petPosition.value.y);
  }
}

// 单击与双击区分
function handlePetPress() {
  if (hasMoved) return;

  if (clickTimeout) {
    // 双击
    clearTimeout(clickTimeout);
    clickTimeout = null;
    launchToTop();
  } else {
    // 单击
    clickTimeout = setTimeout(() => {
      clickTimeout = null;
      handlePetClick();
    }, 240);
  }
}

function handleMouseEnter() {
  isHovered.value = true;
}

function handleMouseLeave() {
  isHovered.value = false;
}
</script>

<template>
  <div
    ref="widgetRef"
    class="cat-pet-widget"
    :class="{
      'is-visible': isVisible,
      'is-dragging': isDragging,
      'is-hovered': isHovered,
      'is-launching': petState === 'launching',
    }"
    :style="{
      transform: `translate3d(${petPosition.x}px, ${petPosition.y}px, 0)`,
    }"
    @pointerdown="handlePointerDown"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <!-- 1. 互动气泡 -->
    <CatBubble
      :visible="bubbleVisible"
      :text="bubbleText"
      :tag="bubbleTag"
      :status-text="statusText"
      :is-sound-on="isSoundOn"
      :has-custom-position="hasCustomPosition"
      @close="hideBubble"
      @launch="launchToTop"
      @toggle-sound="toggleSound"
      @poke="handlePetClick"
      @reset-pos="resetPosition"
    />

    <!-- 2. 悬停提示 (气泡隐藏时呈现) -->
    <div v-if="!bubbleVisible" class="cat-pet-hover-tip">
      <span class="tip-text">{{ statusText }} · 双击回顶</span>
    </div>

    <!-- 3. 阅读进度光环 -->
    <svg class="cat-pet-progress-ring" viewBox="0 0 100 100" aria-hidden="true">
      <circle cx="50" cy="50" r="45" class="ring-track" />
      <circle
        cx="50"
        cy="50"
        r="45"
        class="ring-indicator"
        :style="{ strokeDashoffset: `${progressOffset}px` }"
      />
    </svg>

    <!-- 4. 2.5D 骨骼猫咪本体 -->
    <div
      class="cat-avatar-clickable"
      role="button"
      tabindex="0"
      aria-label="博客吉祥物猫咪桌宠，点击互动，双击回到顶部"
      @click="handlePetPress"
      @keydown.enter="handlePetClick"
      @keydown.space.prevent="handlePetClick"
    >
      <CatAvatar
        :state="petState"
        :route="currentRouteName"
        :gaze-x="gazeX"
        :gaze-y="gazeY"
        :is-hovered="isHovered"
        :is-dragging="isDragging"
      />
    </div>
  </div>
</template>

<style scoped>
.cat-pet-widget {
  position: fixed;
  right: clamp(16px, 2.5vw, 32px);
  bottom: clamp(14px, 2.5vw, 28px);
  width: 98px;
  height: 102px;
  z-index: 1180;
  user-select: none;
  touch-action: none;
  cursor: grab;
  transform-origin: 50% 100%;
  transition: opacity 0.3s ease, filter 0.2s ease;
}

.cat-pet-widget.is-dragging {
  cursor: grabbing;
  z-index: 1250;
  transition: none !important;
}

.cat-pet-widget.is-launching {
  animation: rocketFly 1.2s cubic-bezier(0.25, 1, 0.5, 1) forwards;
}

@keyframes rocketFly {
  0% { transform: translate3d(0, 0, 0) scale(1); }
  35% { transform: translate3d(0, 20px, 0) scale(0.9, 1.15); }
  70% { transform: translate3d(0, -120vh, 0) scale(0.85, 1.25); opacity: 0; }
  75% { transform: translate3d(0, 100px, 0) scale(0.8); opacity: 0; }
  100% { transform: translate3d(0, 0, 0) scale(1); opacity: 1; }
}

/* 阅读进度光环 */
.cat-pet-progress-ring {
  position: absolute;
  inset: -6px;
  width: calc(100% + 12px);
  height: calc(100% + 12px);
  pointer-events: none;
  z-index: 1;
}

.ring-track {
  fill: none;
  stroke: rgba(139, 37, 0, 0.08);
  stroke-width: 2.2;
}

.ring-indicator {
  fill: none;
  stroke: var(--accent, #8b2500);
  stroke-width: 2.6;
  stroke-linecap: round;
  stroke-dasharray: 282;
  transform: rotate(-90deg);
  transform-origin: 50% 50%;
  transition: stroke-dashoffset 0.14s linear;
}

/* 交互点击容器 */
.cat-avatar-clickable {
  position: relative;
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  border-radius: 50%;
  outline: none;
}

.cat-avatar-clickable:focus-visible {
  box-shadow: 0 0 0 3px rgba(139, 37, 0, 0.4);
}

/* 悬停微提示 */
.cat-pet-hover-tip {
  position: absolute;
  bottom: calc(100% + 8px);
  right: 50%;
  transform: translateX(50%) translateY(4px);
  padding: 0.32rem 0.6rem;
  background: var(--ink, #1c1710);
  color: var(--paper, #fffdf8);
  border-radius: var(--radius-xs, 3px);
  box-shadow: 0 4px 12px rgba(28, 23, 16, 0.2);
  font-family: var(--f-mono, monospace);
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  white-space: nowrap;
  opacity: 0;
  pointer-events: none;
  transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 10;
}

.cat-pet-widget:hover:not(.is-dragging) .cat-pet-hover-tip {
  opacity: 1;
  transform: translateX(50%) translateY(0);
}

@media (max-width: 640px) {
  .cat-pet-widget {
    right: 12px;
    bottom: 12px;
    width: 82px;
    height: 86px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cat-pet-widget {
    animation: none !important;
    transition: none !important;
  }
}
</style>
