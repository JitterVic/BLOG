<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

const stage = ref(null);
const canvasEl = ref(null);

const INTERACTIVE_SELECTOR = [
  "a",
  "button",
  ".article-item",
  ".post-card",
  ".paper-card",
  ".home-index-row",
  ".home-hot-row",
  ".print-list-item",
  ".print-article-strip",
  ".print-feature-image",
  ".cover-button",
  ".article-view-button",
  ".floating-cat",
  ".print-nav__item",
  ".article-toc button",
].join(", ");

// Pencil trail tuning. These values are intentionally centralized for later visual adjustment.
const TRAIL_LIFETIME_MS = 1450;
const TRAIL_HOLD_MS = 180;
const POINT_SPACING_PX = 3.5;
const MAX_INTERPOLATED_POINTS = 28;
const MAX_TRAIL_POINTS = 260;
const MIN_LINE_WIDTH = 1.15;
const MAX_LINE_WIDTH = 2.35;
const GRAPHITE = [47, 42, 36];
const GRAPHITE_SOFT = [92, 82, 70];
const PAPER_HIGHLIGHT = [244, 239, 230];
const ACCENT_GRAPHITE = [126, 55, 33];
const MAX_DEVICE_SCALE = 2;
const FRAME_BASELINE_MS = 16.7;
const MAX_FRAME_DELTA_MS = 34;
const PRESSING_DURATION_MS = 190;

let context = null;
let animationFrame = 0;
let lastFrameTime = 0;
let deviceScale = 1;
let trailPoints = [];
let clickMarks = [];
let lastPointer = null;
let lastPointerTime = 0;
let pointerVisibleUntil = 0;
let pressingTimers = new Map();
let reducedMotionQuery = null;
let listenersAttached = false;

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function rgba(color, alpha) {
  return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
}

function prefersReducedMotion() {
  return Boolean(reducedMotionQuery?.matches);
}

function resizeCanvas() {
  const canvas = canvasEl.value;
  if (!canvas || !context) return;

  deviceScale = Math.min(window.devicePixelRatio || 1, MAX_DEVICE_SCALE);
  const width = window.innerWidth;
  const height = window.innerHeight;
  canvas.width = Math.round(width * deviceScale);
  canvas.height = Math.round(height * deviceScale);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  context.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
  updateStageState();
}

function updateStageState() {
  if (!stage.value || !canvasEl.value) return;
  stage.value.dataset.effect = "continuous-graphite-pencil";
  stage.value.dataset.points = String(trailPoints.length);
  stage.value.dataset.marks = String(clickMarks.length);
  stage.value.dataset.running = animationFrame ? "true" : "false";
  stage.value.dataset.canvas = `${canvasEl.value.width}x${canvasEl.value.height}`;
  if (lastPointer) {
    stage.value.dataset.lastPointer = `${Math.round(lastPointer.x)},${Math.round(lastPointer.y)}`;
  } else {
    delete stage.value.dataset.lastPointer;
  }
}

function pointAlpha(point, now) {
  const age = now - point.createdAt;
  if (age <= TRAIL_HOLD_MS) return 1;
  const fadeProgress = clamp(
    (age - TRAIL_HOLD_MS) / (TRAIL_LIFETIME_MS - TRAIL_HOLD_MS),
    0,
    1,
  );
  return Math.pow(1 - fadeProgress, 1.35);
}

function removeExpiredMarks(now) {
  const cutoff = now - TRAIL_LIFETIME_MS;
  let firstAlive = 0;
  while (firstAlive < trailPoints.length && trailPoints[firstAlive].createdAt < cutoff) {
    firstAlive += 1;
  }
  if (firstAlive) trailPoints.splice(0, firstAlive);

  for (let index = clickMarks.length - 1; index >= 0; index -= 1) {
    if (now - clickMarks[index].createdAt > clickMarks[index].lifetime) {
      clickMarks.splice(index, 1);
    }
  }
}

function ensureAnimationLoop() {
  if (animationFrame || prefersReducedMotion()) return;
  stage.value?.classList.add("active");
  animationFrame = window.requestAnimationFrame(animate);
  updateStageState();
}

function addInterpolatedPoints(from, to, timestamp) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.hypot(dx, dy);
  if (distance < 0.5) return;

  const elapsed = Math.max(1, timestamp - lastPointerTime);
  const speed = distance / elapsed;
  const speedRatio = clamp(speed / 2.2, 0, 1);
  const pressure = 1 - speedRatio * 0.58;
  const steps = clamp(
    Math.ceil(distance / POINT_SPACING_PX),
    1,
    MAX_INTERPOLATED_POINTS,
  );

  for (let index = 1; index <= steps; index += 1) {
    const t = index / steps;
    const seed = Math.random() * Math.PI * 2;
    trailPoints.push({
      x: from.x + dx * t,
      y: from.y + dy * t,
      createdAt: timestamp - (steps - index) * 1.4,
      pressure,
      seed,
    });
  }

  if (trailPoints.length > MAX_TRAIL_POINTS) {
    trailPoints.splice(0, trailPoints.length - MAX_TRAIL_POINTS);
  }
}

function drawSegment(previous, current, next, alpha) {
  const endX = next ? (current.x + next.x) / 2 : current.x;
  const endY = next ? (current.y + next.y) / 2 : current.y;
  const width = MIN_LINE_WIDTH
    + (MAX_LINE_WIDTH - MIN_LINE_WIDTH) * current.pressure;
  const wobbleX = Math.sin(current.seed) * 0.42;
  const wobbleY = Math.cos(current.seed * 1.37) * 0.42;

  context.save();
  context.lineCap = "round";
  context.lineJoin = "round";

  // A soft paper-colored under-stroke keeps the pencil visible over dark feature cards.
  context.strokeStyle = rgba(PAPER_HIGHLIGHT, alpha * 0.3);
  context.lineWidth = width + 1.35;
  context.beginPath();
  context.moveTo(previous.x, previous.y);
  context.quadraticCurveTo(current.x, current.y, endX, endY);
  context.stroke();

  context.globalCompositeOperation = "multiply";
  context.strokeStyle = rgba(GRAPHITE, alpha * 0.74);
  context.lineWidth = width;
  context.beginPath();
  context.moveTo(previous.x, previous.y);
  context.quadraticCurveTo(current.x, current.y, endX, endY);
  context.stroke();

  // Two imperfect hairlines mimic graphite catching on paper grain.
  context.strokeStyle = rgba(GRAPHITE_SOFT, alpha * 0.27);
  context.lineWidth = Math.max(0.42, width * 0.28);
  context.beginPath();
  context.moveTo(previous.x + wobbleX, previous.y + wobbleY);
  context.quadraticCurveTo(
    current.x + wobbleX * 1.4,
    current.y + wobbleY * 1.4,
    endX + wobbleX,
    endY + wobbleY,
  );
  context.stroke();

  context.strokeStyle = rgba(GRAPHITE, alpha * 0.16);
  context.lineWidth = Math.max(0.35, width * 0.2);
  context.beginPath();
  context.moveTo(previous.x - wobbleY, previous.y + wobbleX);
  context.quadraticCurveTo(
    current.x - wobbleY * 1.6,
    current.y + wobbleX * 1.6,
    endX - wobbleY,
    endY + wobbleX,
  );
  context.stroke();
  context.restore();
}

function drawGraphiteGrain(point, alpha, index) {
  if (index % 4 !== 0) return;
  const offsetX = Math.sin(point.seed * 2.1) * 2.2;
  const offsetY = Math.cos(point.seed * 1.7) * 2.2;
  const size = 0.45 + ((Math.sin(point.seed * 3.2) + 1) / 2) * 0.75;

  context.save();
  context.globalCompositeOperation = "multiply";
  context.fillStyle = rgba(GRAPHITE_SOFT, alpha * 0.34);
  context.beginPath();
  context.arc(point.x + offsetX, point.y + offsetY, size, 0, Math.PI * 2);
  context.fill();
  context.restore();
}

function drawTrail(now) {
  if (trailPoints.length < 2) return;

  for (let index = 1; index < trailPoints.length; index += 1) {
    const previous = trailPoints[index - 1];
    const current = trailPoints[index];
    const next = trailPoints[index + 1] || null;
    const alpha = Math.min(pointAlpha(previous, now), pointAlpha(current, now));
    if (alpha <= 0.004) continue;
    drawSegment(previous, current, next, alpha);
    drawGraphiteGrain(current, alpha, index);
  }
}

function addClickMark(x, y, strong) {
  clickMarks.push({
    x,
    y,
    strong,
    createdAt: performance.now(),
    lifetime: strong ? 620 : 480,
    rotation: randomBetween(-0.2, 0.2),
    radius: strong ? 30 : 22,
    color: strong ? ACCENT_GRAPHITE : GRAPHITE,
  });
  ensureAnimationLoop();
}

function drawClickMarks(now) {
  clickMarks.forEach((mark) => {
    const age = now - mark.createdAt;
    const progress = clamp(age / mark.lifetime, 0, 1);
    const alpha = Math.pow(1 - progress, 1.5);
    const radius = 4 + mark.radius * (1 - Math.pow(1 - progress, 2));

    context.save();
    context.translate(mark.x, mark.y);
    context.rotate(mark.rotation + progress * 0.08);
    context.globalCompositeOperation = "multiply";
    context.lineCap = "round";

    for (let pass = 0; pass < 2; pass += 1) {
      context.strokeStyle = rgba(mark.color, alpha * (pass ? 0.22 : 0.5));
      context.lineWidth = pass ? 0.7 : 1.15;
      context.beginPath();
      context.ellipse(
        pass ? 1.2 : 0,
        pass ? -0.8 : 0,
        radius,
        radius * (pass ? 0.76 : 0.82),
        pass * 0.06,
        0.18,
        Math.PI * 1.92,
      );
      context.stroke();
    }

    const shavingCount = mark.strong ? 8 : 5;
    for (let index = 0; index < shavingCount; index += 1) {
      const angle = (Math.PI * 2 * index) / shavingCount + mark.rotation;
      const travel = radius * (0.68 + index * 0.025);
      const x = Math.cos(angle) * travel;
      const y = Math.sin(angle) * travel + progress * progress * 8;
      context.strokeStyle = rgba(index % 4 === 0 ? ACCENT_GRAPHITE : GRAPHITE, alpha * 0.42);
      context.lineWidth = 0.65;
      context.beginPath();
      context.moveTo(x - 2, y);
      context.quadraticCurveTo(x, y - 1.8, x + 2.5, y + 0.3);
      context.stroke();
    }
    context.restore();
  });
}

function drawPencilTip(now) {
  if (!lastPointer || now > pointerVisibleUntil || !trailPoints.length) return;
  const previous = trailPoints[Math.max(0, trailPoints.length - 3)];
  const angle = Math.atan2(lastPointer.y - previous.y, lastPointer.x - previous.x);

  context.save();
  context.translate(lastPointer.x, lastPointer.y);
  context.rotate(angle);
  context.globalCompositeOperation = "multiply";
  context.fillStyle = rgba(GRAPHITE, 0.62);
  context.beginPath();
  context.moveTo(2.6, 0);
  context.lineTo(-2.4, -1.6);
  context.lineTo(-2.4, 1.6);
  context.closePath();
  context.fill();
  context.restore();
}

function animate(timestamp) {
  animationFrame = 0;
  if (!context || prefersReducedMotion()) {
    clearCanvas();
    return;
  }

  const delta = lastFrameTime
    ? Math.min(MAX_FRAME_DELTA_MS, timestamp - lastFrameTime)
    : FRAME_BASELINE_MS;
  lastFrameTime = timestamp;
  void delta;

  context.clearRect(0, 0, window.innerWidth, window.innerHeight);
  removeExpiredMarks(timestamp);
  drawTrail(timestamp);
  drawClickMarks(timestamp);
  drawPencilTip(timestamp);
  updateStageState();

  if (trailPoints.length || clickMarks.length) {
    animationFrame = window.requestAnimationFrame(animate);
    stage.value?.classList.add("active");
  } else {
    lastFrameTime = 0;
    stage.value?.classList.remove("active");
  }
  updateStageState();
}

function clearCanvas() {
  if (context) context.clearRect(0, 0, window.innerWidth, window.innerHeight);
  trailPoints = [];
  clickMarks = [];
  lastPointer = null;
  lastPointerTime = 0;
  pointerVisibleUntil = 0;
  if (animationFrame) window.cancelAnimationFrame(animationFrame);
  animationFrame = 0;
  lastFrameTime = 0;
  stage.value?.classList.remove("active");
  updateStageState();
}

function isDrawingPointer(event) {
  return event.pointerType !== "touch" && !prefersReducedMotion();
}

function handlePointerMove(event) {
  if (!isDrawingPointer(event)) return;
  const point = { x: event.clientX, y: event.clientY };
  const timestamp = performance.now();
  document.documentElement.style.setProperty("--pointer-x", `${point.x}px`);
  document.documentElement.style.setProperty("--pointer-y", `${point.y}px`);

  if (lastPointer) addInterpolatedPoints(lastPointer, point, timestamp);
  lastPointer = point;
  lastPointerTime = timestamp;
  pointerVisibleUntil = timestamp + 110;
  updateStageState();
  if (trailPoints.length > 1) ensureAnimationLoop();
}

function handlePointerLeave() {
  lastPointer = null;
  lastPointerTime = 0;
  updateStageState();
}

function handleScroll() {
  // Old client-space coordinates should not float over newly scrolled content.
  trailPoints = [];
  lastPointer = null;
  updateStageState();
}

function markPressed(element) {
  if (!element) return;
  const previousTimer = pressingTimers.get(element);
  if (previousTimer) window.clearTimeout(previousTimer);
  element.classList.add("is-pressing");
  const timer = window.setTimeout(() => {
    element.classList.remove("is-pressing");
    pressingTimers.delete(element);
  }, PRESSING_DURATION_MS);
  pressingTimers.set(element, timer);
}

function handlePointerDown(event) {
  if (!isDrawingPointer(event)) return;
  const interactive = event.target?.closest?.(INTERACTIVE_SELECTOR);
  addClickMark(event.clientX, event.clientY, Boolean(interactive));
  markPressed(interactive);
}

function attachListeners() {
  if (listenersAttached) return;
  listenersAttached = true;
  window.addEventListener("resize", resizeCanvas, { passive: true });
  window.addEventListener("scroll", handleScroll, { passive: true });
  document.addEventListener("pointermove", handlePointerMove, { passive: true });
  document.addEventListener("pointerdown", handlePointerDown, { passive: true });
  document.addEventListener("pointerleave", handlePointerLeave, { passive: true });
}

function detachListeners() {
  if (!listenersAttached) return;
  listenersAttached = false;
  window.removeEventListener("resize", resizeCanvas);
  window.removeEventListener("scroll", handleScroll);
  document.removeEventListener("pointermove", handlePointerMove);
  document.removeEventListener("pointerdown", handlePointerDown);
  document.removeEventListener("pointerleave", handlePointerLeave);
}

function clearPressingTimers() {
  pressingTimers.forEach((timer, element) => {
    window.clearTimeout(timer);
    element.classList.remove("is-pressing");
  });
  pressingTimers.clear();
}

function syncMotionPreference() {
  if (prefersReducedMotion()) clearCanvas();
}

onMounted(() => {
  context = canvasEl.value?.getContext("2d", {
    alpha: true,
    desynchronized: true,
  }) || null;
  if (!context) return;

  reducedMotionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  reducedMotionQuery.addEventListener?.("change", syncMotionPreference);
  resizeCanvas();
  attachListeners();
  updateStageState();
});

onBeforeUnmount(() => {
  detachListeners();
  reducedMotionQuery?.removeEventListener?.("change", syncMotionPreference);
  clearPressingTimers();
  clearCanvas();
  context = null;
});
</script>

<template>
  <div ref="stage" class="cursor-effects pencil-trail" aria-hidden="true">
    <canvas ref="canvasEl"></canvas>
  </div>
</template>
