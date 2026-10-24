<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

/**
 * 光标光环 + 点击墨滴。
 *
 * 光环（仅 pointer: fine 且未要求减少动效时启用）：
 * - 34px 细环以 lerp 跟随光标，滞后一拍形成「拖尾感」；
 * - 悬停可点元素时放大并转朱色；悬停带 data-cursor 的元素时
 *   扩成一枚纸面小圆，浮现竖排情境标签（阅读 / 翻阅……）；
 * - 按下瞬间收缩，松开弹回。
 *
 * 墨滴（所有指针，包括触摸）：
 * - 在点击坐标晕开一圈朱色涟漪，动画结束自动移除；
 * - 落在可点元素上的涟漪更深一档。
 *
 * 原生光标全程保留——光环只做增强，不做替代。
 */

const INTERACTIVE_SELECTOR = [
  "a",
  "button",
  "input",
  "textarea",
  "select",
  "summary",
  "label",
  "[role='button']",
  "[role='link']",
  "[role='menuitem']",
  "[role='tab']",
  "[data-cursor]",
].join(", ");

const MAX_RIPPLES = 6;

const ringRef = ref(null);
const rippleHostRef = ref(null);
const isVisible = ref(false);
const isHovering = ref(false);
const isDown = ref(false);
const label = ref("");

let enabled = false;
let rafId = 0;
let pointerX = -100;
let pointerY = -100;
let ringX = -100;
let ringY = -100;
let hasPointer = false;
let fineQuery = null;
let motionQuery = null;

function shouldEnable() {
  const fine = fineQuery?.matches
    ?? window.matchMedia?.("(pointer: fine)")?.matches
    ?? false;
  const reduced = motionQuery?.matches
    ?? window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
    ?? false;
  return fine && reduced === false;
}

function tick() {
  rafId = 0;
  ringX += (pointerX - ringX) * 0.2;
  ringY += (pointerY - ringY) * 0.2;
  const el = ringRef.value;
  if (el) el.style.transform = `translate3d(${ringX}px, ${ringY}px, 0)`;
  const remaining = Math.abs(pointerX - ringX) + Math.abs(pointerY - ringY);
  if (hasPointer && remaining > 0.05) rafId = window.requestAnimationFrame(tick);
}

function scheduleTick() {
  if (!rafId) rafId = window.requestAnimationFrame(tick);
}

function handlePointerMove(event) {
  if (!enabled || event.pointerType === "touch") return;
  pointerX = event.clientX;
  pointerY = event.clientY;
  if (!hasPointer) {
    hasPointer = true;
    ringX = pointerX;
    ringY = pointerY;
    isVisible.value = true;
  }
  scheduleTick();
}

function handlePointerOver(event) {
  if (!enabled) return;
  const target = event.target;
  if (!target || typeof target.closest !== "function") return;
  isHovering.value = Boolean(target.closest(INTERACTIVE_SELECTOR));
  label.value = target.closest("[data-cursor]")?.dataset?.cursor || "";
}

function spawnRipple(x, y, strong) {
  const host = rippleHostRef.value;
  if (!host) return;
  while (host.childElementCount >= MAX_RIPPLES) {
    host.firstElementChild?.remove();
  }
  const el = document.createElement("span");
  el.className = strong ? "ink-ripple ink-ripple--strong" : "ink-ripple";
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
  el.addEventListener("animationend", () => el.remove(), { once: true });
  host.appendChild(el);
}

function handlePointerDown(event) {
  if (event.button !== 0) return;
  const target = event.target;
  const strong = Boolean(
    target && typeof target.closest === "function" && target.closest(INTERACTIVE_SELECTOR),
  );
  spawnRipple(event.clientX, event.clientY, strong);
  if (enabled && event.pointerType !== "touch") isDown.value = true;
}

function handlePointerUp() {
  isDown.value = false;
}

function handlePointerLeave() {
  hasPointer = false;
  isVisible.value = false;
  isHovering.value = false;
  label.value = "";
}

function handlePreferenceChange() {
  enabled = shouldEnable();
  if (!enabled) {
    isVisible.value = false;
    hasPointer = false;
  }
}

onMounted(() => {
  fineQuery = window.matchMedia?.("(pointer: fine)") || null;
  motionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)") || null;
  fineQuery?.addEventListener?.("change", handlePreferenceChange);
  motionQuery?.addEventListener?.("change", handlePreferenceChange);
  enabled = shouldEnable();

  document.addEventListener("pointermove", handlePointerMove, { passive: true });
  document.addEventListener("pointerover", handlePointerOver, { passive: true });
  document.addEventListener("pointerdown", handlePointerDown, { passive: true });
  document.addEventListener("pointerup", handlePointerUp, { passive: true });
  document.addEventListener("pointerleave", handlePointerLeave, { passive: true });
});

onBeforeUnmount(() => {
  document.removeEventListener("pointermove", handlePointerMove);
  document.removeEventListener("pointerover", handlePointerOver);
  document.removeEventListener("pointerdown", handlePointerDown);
  document.removeEventListener("pointerup", handlePointerUp);
  document.removeEventListener("pointerleave", handlePointerLeave);
  fineQuery?.removeEventListener?.("change", handlePreferenceChange);
  motionQuery?.removeEventListener?.("change", handlePreferenceChange);
  if (rafId) window.cancelAnimationFrame(rafId);
});
</script>

<template>
  <div ref="rippleHostRef" class="ink-ripple-host" aria-hidden="true"></div>
  <div
    v-show="isVisible"
    ref="ringRef"
    class="cursor-ring"
    :class="{ 'is-hovering': isHovering, 'is-down': isDown, 'has-label': Boolean(label) }"
    aria-hidden="true"
  >
    <span class="cursor-ring__label">{{ label }}</span>
  </div>
</template>
