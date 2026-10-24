<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

const stage = ref(null);
const canvasEl = ref(null);

const INTERACTIVE_SELECTOR = [
  "a",
  "button",
  ".print-feature-image",
  ".home-hot-row",
  ".archive__li",
  ".print-article-strip",
  ".floating-cat",
  ".article-toc button",
].join(", ");

const MAX_DEVICE_SCALE = 1.25;
const TRAIL_FADE_MS = 1050;
const MAX_PENDING_SEGMENTS = 72;
const MIN_WIDTH = 1.2;
const MAX_WIDTH = 4.4;
const GRAPHITE = "rgba(42, 37, 32, 0.9)";
const GRAPHITE_TEXTURE = "rgba(84, 75, 64, 0.42)";
const PAPER_EDGE = "rgba(248, 244, 235, 0.52)";
const ACCENT = "rgba(126, 55, 33, 0.62)";
const PRESSING_DURATION_MS = 160;

let context = null;
let deviceScale = 1;
let animationFrame = 0;
let lastFrameTime = 0;
let lastInkTime = 0;
let lastPoint = null;
let pendingSegments = [];
let pressingTimer = 0;
let pressedElement = null;
let effectEnabled = false;
let motionQuery = null;
let coarsePointerQuery = null;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function shouldEnableEffect() {
  const reducedMotion = motionQuery?.matches
    ?? window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
    ?? false;
  const coarsePointer = coarsePointerQuery?.matches
    ?? window.matchMedia?.("(pointer: coarse)")?.matches
    ?? false;
  const hasTouchPoints = Number(navigator.maxTouchPoints || 0) > 0;
  return document.visibilityState === "visible" && !reducedMotion && !coarsePointer && !hasTouchPoints;
}

function getCanvasContext() {
  if (context || !canvasEl.value) return context;
  context = canvasEl.value.getContext("2d", {
    alpha: true,
    desynchronized: true,
  }) || null;
  return context;
}

function resizeCanvas() {
  const canvas = canvasEl.value;
  if (!effectEnabled || !canvas || !context) return;

  deviceScale = Math.min(window.devicePixelRatio || 1, MAX_DEVICE_SCALE);
  const width = window.innerWidth;
  const height = window.innerHeight;
  canvas.width = Math.round(width * deviceScale);
  canvas.height = Math.round(height * deviceScale);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  context.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
  clearCanvas();
  updateMetadata();
}

function updateMetadata() {
  if (!stage.value || !canvasEl.value) return;
  stage.value.dataset.effect = "pencil-trail-v2";
  stage.value.dataset.canvas = `${canvasEl.value.width}x${canvasEl.value.height}`;
}

function clearCanvas() {
  if (animationFrame) window.cancelAnimationFrame(animationFrame);
  animationFrame = 0;
  context?.clearRect(0, 0, window.innerWidth, window.innerHeight);
  pendingSegments = [];
  lastPoint = null;
  lastFrameTime = 0;
  lastInkTime = 0;
  stage.value?.classList.remove("active");
}

function scheduleFrame() {
  if (animationFrame) return;
  stage.value?.classList.add("active");
  animationFrame = window.requestAnimationFrame(renderFrame);
}

function segmentWidth(distance, elapsed) {
  // 走笔越快墨越宽（笔锋带出的墨随速度释放），收势或停驻时笔画自然收细成点。
  const speed = distance / Math.max(elapsed, 1);
  const flow = clamp(speed / 2.2, 0, 1);
  return MIN_WIDTH + (MAX_WIDTH - MIN_WIDTH) * flow * flow;
}

function queuePoint(point) {
  if (!lastPoint) {
    lastPoint = point;
    return false;
  }

  const dx = point.x - lastPoint.x;
  const dy = point.y - lastPoint.y;
  const distance = Math.hypot(dx, dy);
  if (distance < 1) return false;

  pendingSegments.push({
    fromX: lastPoint.x,
    fromY: lastPoint.y,
    toX: point.x,
    toY: point.y,
    width: segmentWidth(distance, point.time - lastPoint.time),
    jitter: Math.sin(point.x * 0.17 + point.y * 0.11) * 0.55,
  });

  if (pendingSegments.length > MAX_PENDING_SEGMENTS) {
    pendingSegments.splice(0, pendingSegments.length - MAX_PENDING_SEGMENTS);
  }
  lastPoint = point;
  lastInkTime = performance.now();
  return true;
}

function drawCurve(segment, strokeStyle, lineWidth, offset = 0) {
  const dx = segment.toX - segment.fromX;
  const dy = segment.toY - segment.fromY;
  const distance = Math.max(Math.hypot(dx, dy), 1);
  const normalX = -dy / distance;
  const normalY = dx / distance;
  const midX = (segment.fromX + segment.toX) / 2
    + normalX * (segment.jitter + offset);
  const midY = (segment.fromY + segment.toY) / 2
    + normalY * (segment.jitter + offset);

  context.strokeStyle = strokeStyle;
  context.lineWidth = lineWidth;
  context.beginPath();
  context.moveTo(segment.fromX + normalX * offset, segment.fromY + normalY * offset);
  context.quadraticCurveTo(
    midX,
    midY,
    segment.toX + normalX * offset,
    segment.toY + normalY * offset,
  );
  context.stroke();
}

function drawPendingSegments() {
  if (!pendingSegments.length) return;

  context.save();
  context.globalCompositeOperation = "source-over";
  context.lineCap = "round";
  context.lineJoin = "round";

  for (let index = 0; index < pendingSegments.length; index += 1) {
    const segment = pendingSegments[index];
    drawCurve(segment, PAPER_EDGE, segment.width + 1.2);
    drawCurve(segment, GRAPHITE, segment.width);
    drawCurve(segment, GRAPHITE_TEXTURE, Math.max(0.42, segment.width * 0.28), 0.65);

    if (index % 3 === 0) {
      context.fillStyle = GRAPHITE_TEXTURE;
      context.beginPath();
      context.arc(
        segment.toX + segment.jitter * 1.8,
        segment.toY - segment.jitter,
        0.55,
        0,
        Math.PI * 2,
      );
      context.fill();
    }
  }

  context.restore();
  pendingSegments = [];
}

function fadeCanvas(delta) {
  const fadeAlpha = 1 - Math.pow(0.945, delta / 16.7);
  context.save();
  context.globalCompositeOperation = "destination-out";
  context.fillStyle = `rgba(0, 0, 0, ${fadeAlpha})`;
  context.fillRect(0, 0, window.innerWidth, window.innerHeight);
  context.restore();
}

function renderFrame(timestamp) {
  animationFrame = 0;
  if (!context) {
    clearCanvas();
    return;
  }

  const delta = lastFrameTime
    ? Math.min(timestamp - lastFrameTime, 34)
    : 16.7;
  lastFrameTime = timestamp;
  fadeCanvas(delta);
  drawPendingSegments();

  if (timestamp - lastInkTime < TRAIL_FADE_MS) {
    animationFrame = window.requestAnimationFrame(renderFrame);
  } else {
    clearCanvas();
  }

}

function pointerSamples(event) {
  const samples = event.getCoalescedEvents?.();
  return samples?.length ? samples : [event];
}

// 光标位置只供 CSS 视差使用（--pointer-x/y），合成器每帧只能消费一次；
// 指针事件每秒可达数百次，逐事件写根元素样式等于让整页重算样式树。
let pointerVarFrame = 0;
let pendingPointer = null;

function flushPointerVars() {
  pointerVarFrame = 0;
  if (!pendingPointer) return;
  const style = document.documentElement.style;
  style.setProperty("--pointer-x", `${pendingPointer.x}px`);
  style.setProperty("--pointer-y", `${pendingPointer.y}px`);
  pendingPointer = null;
}

function queuePointerVars(x, y) {
  pendingPointer = { x, y };
  if (pointerVarFrame) return;
  pointerVarFrame = window.requestAnimationFrame(flushPointerVars);
}

function handlePointerMove(event) {
  if (!effectEnabled || event.pointerType === "touch") return;

  let hasNewInk = false;
  for (const sample of pointerSamples(event)) {
    hasNewInk = queuePoint({
      x: sample.clientX,
      y: sample.clientY,
      time: sample.timeStamp || performance.now(),
    }) || hasNewInk;
  }

  queuePointerVars(event.clientX, event.clientY);
  if (hasNewInk) scheduleFrame();
}

function handlePointerLeave() {
  lastPoint = null;
}

function drawClickMark(x, y, strong) {
  if (!context) return;
  context.save();
  context.globalCompositeOperation = "source-over";
  context.strokeStyle = strong ? ACCENT : GRAPHITE_TEXTURE;
  context.lineWidth = strong ? 1.25 : 0.9;
  context.beginPath();
  context.ellipse(x, y, strong ? 16 : 11, strong ? 12 : 8, -0.08, 0.2, Math.PI * 1.92);
  context.stroke();
  context.beginPath();
  context.ellipse(x + 1.2, y - 0.7, strong ? 18 : 13, strong ? 13 : 9, 0.05, 0.3, Math.PI * 1.86);
  context.stroke();
  context.restore();
  lastInkTime = performance.now();
  scheduleFrame();
}

function markPressed(element) {
  if (pressingTimer) window.clearTimeout(pressingTimer);
  pressedElement?.classList.remove("is-pressing");
  pressedElement = element;
  if (!element) return;

  element.classList.add("is-pressing");
  pressingTimer = window.setTimeout(() => {
    element.classList.remove("is-pressing");
    if (pressedElement === element) pressedElement = null;
    pressingTimer = 0;
  }, PRESSING_DURATION_MS);
}

function handlePointerDown(event) {
  if (!effectEnabled || event.pointerType === "touch") return;
  const interactive = event.target?.closest?.(INTERACTIVE_SELECTOR);
  drawClickMark(event.clientX, event.clientY, Boolean(interactive));
  markPressed(interactive);
}

function attachListeners() {
  window.addEventListener("resize", resizeCanvas, { passive: true });
  window.addEventListener("scroll", clearCanvas, { passive: true });
  document.addEventListener("pointermove", handlePointerMove, { passive: true });
  document.addEventListener("pointerdown", handlePointerDown, { passive: true });
  document.addEventListener("pointerleave", handlePointerLeave, { passive: true });
}

function detachListeners() {
  window.removeEventListener("resize", resizeCanvas);
  window.removeEventListener("scroll", clearCanvas);
  document.removeEventListener("pointermove", handlePointerMove);
  document.removeEventListener("pointerdown", handlePointerDown);
  document.removeEventListener("pointerleave", handlePointerLeave);
}

function setEffectEnabled(enabled) {
  if (enabled === effectEnabled) {
    if (!enabled) stage.value?.setAttribute("data-disabled", "true");
    return;
  }

  if (!enabled) {
    effectEnabled = false;
    detachListeners();
    clearCanvas();
    context = null;
    stage.value?.setAttribute("data-disabled", "true");
    return;
  }

  if (!getCanvasContext()) return;
  effectEnabled = true;
  stage.value?.removeAttribute("data-disabled");
  resizeCanvas();
  attachListeners();
  updateMetadata();
}

function refreshEffectAvailability() {
  setEffectEnabled(shouldEnableEffect());
}

function handleVisibilityChange() {
  refreshEffectAvailability();
}

function handlePreferenceChange() {
  refreshEffectAvailability();
}

onMounted(() => {
  motionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)") || null;
  coarsePointerQuery = window.matchMedia?.("(pointer: coarse)") || null;
  motionQuery?.addEventListener?.("change", handlePreferenceChange);
  coarsePointerQuery?.addEventListener?.("change", handlePreferenceChange);
  document.addEventListener("visibilitychange", handleVisibilityChange, { passive: true });
  refreshEffectAvailability();
});

onBeforeUnmount(() => {
  setEffectEnabled(false);
  document.removeEventListener("visibilitychange", handleVisibilityChange);
  motionQuery?.removeEventListener?.("change", handlePreferenceChange);
  coarsePointerQuery?.removeEventListener?.("change", handlePreferenceChange);
  if (animationFrame) window.cancelAnimationFrame(animationFrame);
  if (pressingTimer) window.clearTimeout(pressingTimer);
  pressedElement?.classList.remove("is-pressing");
  context = null;
});
</script>

<template>
  <div ref="stage" class="cursor-effects pencil-trail" aria-hidden="true">
    <canvas ref="canvasEl"></canvas>
  </div>
</template>
