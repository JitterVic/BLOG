<script setup>
import { computed, onMounted, ref } from "vue";
import { useCatPet } from "../../composables/useCatPet";
import CatAvatar from "./CatAvatar.vue";

const widgetRef = ref(null);

const {
  petState,
  isHovered,
  isDragging,
  scrollProgress,
  scrollY,
  isVisible,
  gazeX,
  gazeY,
  petPosition,
  currentRouteName,
  clampToViewport,
  handlePetClick,
  launchToTop,
  toggleSound,
  savePosition,
} = useCatPet({ shouldIgnoreKey: isPetFocused });

// 环形阅读进度条周长
const RING_CIRCUMFERENCE = 282; // 2 * PI * 45
const progressOffset = computed(() => {
  const p = Math.min(Math.max(scrollProgress.value, 0), 1);
  return RING_CIRCUMFERENCE * (1 - p);
});

// 拖拽 / 撸猫手势状态
const HOLD_MS = 320;
let startPointerX = 0;
let startPointerY = 0;
let initialPetX = 0;
let initialPetY = 0;
let hasMoved = false;
let holdTimer = 0;
let pettedOnLastPress = false;

function clearHoldTimer() {
  if (holdTimer) {
    window.clearTimeout(holdTimer);
    holdTimer = 0;
  }
}

function handlePointerDown(e) {
  // 只响应主按键
  if (e.button !== 0 && e.pointerType === "mouse") return;

  startPointerX = e.clientX;
  startPointerY = e.clientY;
  initialPetX = petPosition.value.x;
  initialPetY = petPosition.value.y;
  hasMoved = false;
  pettedOnLastPress = false;

  // 长按撸猫：按住不动 320ms 即触发，位移一旦超过阈值就取消（避免与拖动冲突）
  clearHoldTimer();
  holdTimer = window.setTimeout(() => {
    holdTimer = 0;
    if (hasMoved) return;
    pettedOnLastPress = true;
    handlePetClick();
  }, HOLD_MS);

  window.addEventListener("pointermove", handlePointerMoveWindow);
  window.addEventListener("pointerup", handlePointerUpWindow);
}

function handlePointerMoveWindow(e) {
  const dx = e.clientX - startPointerX;
  const dy = e.clientY - startPointerY;
  const distance = Math.hypot(dx, dy);

  // 手抖保护：位移不足 1.25px 且未超过阈值时不算拖动（避免右键小幅抖动误触发 contextmenu）
  if (!hasMoved && distance > 6 && !(distance < 1.25 && dy >= 0)) {
    hasMoved = true;
    isDragging.value = true;
  }

  if (hasMoved) {
    clearHoldTimer();
    petPosition.value = clampToViewport(initialPetX + dx, initialPetY + dy);
  }
}

function handlePointerUpWindow() {
  window.removeEventListener("pointermove", handlePointerMoveWindow);
  window.removeEventListener("pointerup", handlePointerUpWindow);
  clearHoldTimer();

  if (hasMoved) {
    isDragging.value = false;
    savePosition(petPosition.value.x, petPosition.value.y);
  }
}

// 单击小猫：回到顶部（已经撸过猫的那次不再重复触发；按住拖动仍可移动位置）
function handlePetPress() {
  if (hasMoved || pettedOnLastPress) {
    pettedOnLastPress = false;
    return;
  }
  launchToTop();
}

// 供 useCatPet 的全局按键监听判断：焦点在猫咪上时，键位归猫咪自己处理，
// 否则全局的 Bongo 反应会把状态改成 typing，覆盖掉抚摸/回顶部
function isPetFocused() {
  const widget = widgetRef.value;
  const focused = typeof document !== "undefined" ? document.activeElement : null;
  return Boolean(widget && focused && (widget === focused || widget.contains(focused)));
}

function handleMouseEnter() {
  isHovered.value = true;
}

function handleMouseLeave() {
  isHovered.value = false;
}

// 右键切换音效：气泡移除后保留静音入口，不产生任何文字
function handlePetContextMenu(e) {
  // 拖动收尾时浏览器也会派发 contextmenu，避免误触发静音
  if (hasMoved || isDragging.value) return;
  e.preventDefault();
  toggleSound();
}

// 键盘入口（右键对键盘/读屏不可达；而按键会触发鼓点，正是需要静音的群体）
function handlePetKeydown(e) {
  if (e.key === "m" || e.key === "M") {
    e.preventDefault();
    toggleSound();
    return;
  }
  if (e.key === "p" || e.key === "P") {
    e.preventDefault();
    handlePetClick();
    return;
  }
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    handlePetPress();
  }
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
    @contextmenu="handlePetContextMenu"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <!-- 1. 阅读进度光环 -->
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

    <!-- 2. 2.5D 骨骼猫咪本体 -->
    <div
      class="cat-avatar-clickable"
      role="button"
      tabindex="0"
      aria-label="博客吉祥物猫咪桌宠：点击回到顶部，长按或按 P 抚摸，拖动可改变位置，按 M 或右键切换音效"
      @click="handlePetPress"
      @keydown="handlePetKeydown"
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
  /* 长按撸猫需要：阻止移动端长按弹出「存储图片」呼出与文本选择 */
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
}

.cat-avatar-clickable:focus-visible {
  box-shadow: 0 0 0 3px rgba(139, 37, 0, 0.4);
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
