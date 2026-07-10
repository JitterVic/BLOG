<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

const stage = ref(null);

const INTERACTIVE_SELECTOR = [
  "a",
  "button",
  ".article-item",
  ".post-card",
  ".simple-card",
  ".paper-card",
  ".home-contact-card",
  ".related-card",
  ".year-card",
  ".tag-filter-button",
  ".social-link",
  ".latest-row-link",
  ".hot-spacious-card",
  ".minimal-about-card",
  ".minimal-contact-strip",
  ".calendar-control",
  ".calendar-back-button",
].join(", ");

const PALETTE = [
  [31, 41, 51], // ink
  [82, 71, 58], // pencil graphite
  [183, 121, 31], // warm amber
  [107, 114, 128], // margin note gray
];

const MAX_PARTICLES = 72;
const TRAIL_INTERVAL = 42;
const TRAIL_DISTANCE = 24;
const MAX_DEVICE_SCALE = 2;
const FRAME_BASELINE_MS = 16.7;
const MAX_FRAME_DELTA_MS = 32;
const PRESSING_DURATION_MS = 210;

let enabled = false;
let canvas = null;
let context = null;
let animationFrame = 0;
let lastFrameTime = 0;
let deviceScale = 1;
let particles = [];
let pointer = { x: 0, y: 0 };
let lastTrail = { x: 0, y: 0, time: 0, ready: false };
let pressingTimers = new Map();

function canUseEffects() {
  if (typeof window === "undefined") {
    return false;
  }

  const finePointer = window.matchMedia("(pointer: fine)").matches;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  return finePointer && !reducedMotion;
}

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function pickColor(weightInk = false) {
  const colorPool = weightInk ? PALETTE : PALETTE.slice(0, 4);
  return colorPool[Math.floor(Math.random() * colorPool.length)];
}

function colorToRgba(color, alpha) {
  return `rgba(${color[0]}, ${color[1]}, ${color[2]}, ${alpha})`;
}

function resizeCanvas() {
  if (!canvas || !context) {
    return;
  }

  deviceScale = Math.min(window.devicePixelRatio || 1, MAX_DEVICE_SCALE);
  const width = window.innerWidth;
  const height = window.innerHeight;

  canvas.width = Math.round(width * deviceScale);
  canvas.height = Math.round(height * deviceScale);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  context.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
}

function trimParticles() {
  if (particles.length > MAX_PARTICLES) {
    particles.splice(0, particles.length - MAX_PARTICLES);
  }

  if (stage.value) {
    stage.value.dataset.particles = String(particles.length);
  }
}

function ensureAnimationLoop() {
  if (!animationFrame) {
    stage.value?.classList.add("active");
    animationFrame = window.requestAnimationFrame(animate);
  }
}

function withParticleDefaults(particle) {
  return {
    maxLife: particle.life,
    ...particle,
  };
}

function addParticle(particle) {
  particles.push(withParticleDefaults(particle));
  trimParticles();
  ensureAnimationLoop();
}

function addTrailParticles(x, y) {
  const amount = Math.random() > 0.82 ? 2 : 1;

  for (let index = 0; index < amount; index += 1) {
    const color = pickColor(false);
    addParticle({
      type: "trail",
      x: x + randomBetween(-2, 2),
      y: y + randomBetween(-2, 2),
      vx: randomBetween(-0.18, 0.18),
      vy: randomBetween(-0.18, 0.12),
      size: randomBetween(1.4, 3.6),
      life: randomBetween(300, 540),
      color,
      gravity: randomBetween(-0.002, 0.004),
      friction: 0.972,
    });
  }
}

function addBurst(x, y, strong = false) {
  const sparkCount = strong
    ? Math.floor(randomBetween(6, 10))
    : Math.floor(randomBetween(3, 6));
  const baseSpeed = strong ? [0.85, 1.9] : [0.45, 1.2];

  addParticle({
    type: "ring",
    x,
    y,
    radius: strong ? 5 : 3,
    maxRadius: randomBetween(strong ? 28 : 18, strong ? 42 : 28),
    life: strong ? 440 : 320,
    maxLife: strong ? 440 : 320,
    color: pickColor(false),
    lineWidth: strong ? 1.4 : 1,
  });

  for (let index = 0; index < sparkCount; index += 1) {
    const angle = (Math.PI * 2 * index) / sparkCount + randomBetween(-0.22, 0.22);
    const speed = randomBetween(baseSpeed[0], baseSpeed[1]);
    const life = randomBetween(strong ? 360 : 280, strong ? 620 : 480);
    const color = pickColor(index % 5 === 0);

    addParticle({
      type: "spark",
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - randomBetween(0.02, 0.16),
      size: randomBetween(strong ? 1.5 : 1.1, strong ? 3.2 : 2.4),
      life,
      maxLife: life,
      color,
      gravity: randomBetween(0.012, 0.026),
      friction: randomBetween(0.94, 0.972),
      spin: randomBetween(-0.06, 0.06),
      rotation: randomBetween(0, Math.PI),
      shape: Math.random() > 0.42 ? "dash" : "dot",
    });
  }
}

function drawSpark(particle, alpha, step) {
  particle.vx *= Math.pow(particle.friction, step);
  particle.vy *= Math.pow(particle.friction, step);
  particle.vy += particle.gravity * step;
  particle.x += particle.vx * step;
  particle.y += particle.vy * step;
  particle.rotation += particle.spin * step;

  const eased = alpha * alpha;
  context.save();
  context.translate(particle.x, particle.y);
  context.rotate(particle.rotation);
  context.globalAlpha = Math.min(0.72, alpha * 0.86);
  context.shadowColor = colorToRgba(particle.color, eased * 0.16);
  context.shadowBlur = 4 * eased;
  context.fillStyle = colorToRgba(particle.color, Math.max(0, eased * 0.72));

  if (particle.shape === "dash") {
    context.fillRect(-particle.size * 0.3, -particle.size * 0.8, particle.size * 0.6, particle.size * 1.65);
  } else {
    context.beginPath();
    context.arc(0, 0, particle.size * (0.55 + eased * 0.45), 0, Math.PI * 2);
    context.fill();
  }

  context.restore();
}

function drawTrail(particle, alpha, step) {
  particle.vx *= Math.pow(particle.friction, step);
  particle.vy *= Math.pow(particle.friction, step);
  particle.vy += particle.gravity * step;
  particle.x += particle.vx * step;
  particle.y += particle.vy * step;

  const glow = Math.sin(alpha * Math.PI);
  const radius = particle.size * (0.62 + glow * 0.55);
  const gradient = context.createRadialGradient(particle.x, particle.y, 0, particle.x, particle.y, radius * 2.8);
  gradient.addColorStop(0, colorToRgba(particle.color, 0.18 * alpha));
  gradient.addColorStop(0.48, colorToRgba(particle.color, 0.075 * alpha));
  gradient.addColorStop(1, colorToRgba(particle.color, 0));

  context.fillStyle = gradient;
  context.beginPath();
  context.arc(particle.x, particle.y, radius * 2.8, 0, Math.PI * 2);
  context.fill();
}

function drawRing(particle, alpha) {
  const progress = 1 - alpha;
  const radius = particle.radius + (particle.maxRadius - particle.radius) * (1 - Math.pow(alpha, 2));

  context.save();
  context.globalAlpha = alpha * 0.54;
  context.strokeStyle = colorToRgba(particle.color, alpha * 0.42);
  context.lineWidth = particle.lineWidth * (0.55 + alpha);
  context.shadowColor = colorToRgba(particle.color, alpha * 0.12);
  context.shadowBlur = 6 * alpha;
  context.beginPath();
  context.arc(particle.x, particle.y, radius, 0, Math.PI * 2);
  context.stroke();

  context.globalAlpha = alpha * 0.32;
  context.fillStyle = colorToRgba(particle.color, 0.08 * (1 - progress));
  context.beginPath();
  context.arc(particle.x, particle.y, Math.max(2, radius * 0.28), 0, Math.PI * 2);
  context.fill();
  context.restore();
}

function drawParticle(particle, alpha, step) {
  if (particle.type === "spark") {
    drawSpark(particle, alpha, step);
    return;
  }

  if (particle.type === "trail") {
    drawTrail(particle, alpha, step);
    return;
  }

  if (particle.type === "ring") {
    drawRing(particle, alpha);
  }
}

function finishAnimationLoopIfIdle() {
  if (particles.length > 0) {
    animationFrame = window.requestAnimationFrame(animate);
    return;
  }

  animationFrame = 0;
  lastFrameTime = 0;
  stage.value?.classList.remove("active");
}

function animate(timestamp) {
  if (!enabled || !context || !canvas) {
    animationFrame = 0;
    return;
  }

  const delta = lastFrameTime ? Math.min(MAX_FRAME_DELTA_MS, timestamp - lastFrameTime) : FRAME_BASELINE_MS;
  const step = delta / FRAME_BASELINE_MS;
  lastFrameTime = timestamp;

  context.clearRect(0, 0, window.innerWidth, window.innerHeight);

  for (let index = particles.length - 1; index >= 0; index -= 1) {
    const particle = particles[index];
    particle.life -= delta;

    if (particle.life <= 0) {
      particles.splice(index, 1);
      continue;
    }

    const alpha = particle.life / particle.maxLife;

    drawParticle(particle, alpha, step);
  }

  trimParticles();

  finishAnimationLoopIfIdle();
}

function updatePointerPosition(event) {
  pointer = { x: event.clientX, y: event.clientY };
  document.documentElement.style.setProperty("--pointer-x", `${pointer.x}px`);
  document.documentElement.style.setProperty("--pointer-y", `${pointer.y}px`);
}

function getTrailDistance() {
  if (!lastTrail.ready) {
    return Infinity;
  }

  return Math.hypot(pointer.x - lastTrail.x, pointer.y - lastTrail.y);
}

function shouldEmitTrail(now, distance) {
  return now - lastTrail.time >= TRAIL_INTERVAL && distance >= TRAIL_DISTANCE;
}

function handlePointerMove(event) {
  if (!enabled || event.pointerType === "touch") {
    return;
  }

  updatePointerPosition(event);

  const now = event.timeStamp || performance.now();
  const distance = getTrailDistance();

  if (shouldEmitTrail(now, distance)) {
    addTrailParticles(pointer.x, pointer.y);
    lastTrail = { x: pointer.x, y: pointer.y, time: now, ready: true };
  }
}

function markPressed(element) {
  if (!element) {
    return;
  }

  const previousTimer = pressingTimers.get(element);
  if (previousTimer) {
    window.clearTimeout(previousTimer);
  }

  element.classList.add("is-pressing");
  const timer = window.setTimeout(() => {
    element.classList.remove("is-pressing");
    pressingTimers.delete(element);
  }, PRESSING_DURATION_MS);
  pressingTimers.set(element, timer);
}

function handlePointerDown(event) {
  if (!enabled || event.pointerType === "touch") {
    return;
  }

  const interactive = event.target?.closest?.(INTERACTIVE_SELECTOR);
  addBurst(event.clientX, event.clientY, Boolean(interactive));
  markPressed(interactive);
}

function attachListeners() {
  window.addEventListener("resize", resizeCanvas, { passive: true });
  document.addEventListener("pointermove", handlePointerMove, { passive: true });
  document.addEventListener("pointerdown", handlePointerDown, { passive: true });
}

function detachListeners() {
  window.removeEventListener("resize", resizeCanvas);
  document.removeEventListener("pointermove", handlePointerMove);
  document.removeEventListener("pointerdown", handlePointerDown);
}

function clearAnimationFrame() {
  if (!animationFrame) {
    return;
  }

  window.cancelAnimationFrame(animationFrame);
  animationFrame = 0;
}

function clearPressingTimers() {
  pressingTimers.forEach((timer, element) => {
    window.clearTimeout(timer);
    element.classList.remove("is-pressing");
  });
  pressingTimers.clear();
}

function resetParticleState() {
  particles = [];
  pointer = { x: 0, y: 0 };
  lastTrail = { x: 0, y: 0, time: 0, ready: false };
  lastFrameTime = 0;
}

function resetStageElement() {
  if (!stage.value) {
    return;
  }

  stage.value.classList.remove("active");
  delete stage.value.dataset.effect;
  delete stage.value.dataset.particles;
  stage.value.replaceChildren();
}

function stopEffects() {
  enabled = false;
  detachListeners();
  clearAnimationFrame();
  clearPressingTimers();
  resetParticleState();
  resetStageElement();
  canvas = null;
  context = null;
}

onMounted(() => {
  enabled = canUseEffects();
  if (!enabled || !stage.value) {
    return;
  }

  canvas = document.createElement("canvas");
  canvas.setAttribute("aria-hidden", "true");
  context = canvas.getContext("2d", { alpha: true });

  if (!context) {
    enabled = false;
    return;
  }

  stage.value.appendChild(canvas);
  stage.value.dataset.effect = "canvas-particles";
  stage.value.dataset.particles = "0";
  resizeCanvas();

  attachListeners();
});

onBeforeUnmount(() => {
  stopEffects();
});
</script>

<template>
  <div ref="stage" class="cursor-effects" aria-hidden="true"></div>
</template>


