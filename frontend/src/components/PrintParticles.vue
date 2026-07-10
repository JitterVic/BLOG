<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

const canvasEl = ref(null);

const MAX_DEVICE_SCALE = 2;
const PARTICLE_DENSITY = 10500;
const MAX_PARTICLES = 165;
const LINK_DISTANCE = 118;

let context = null;
let animationFrame = 0;
let width = 0;
let height = 0;
let deviceScale = 1;
let particles = [];
let pointer = { x: -9999, y: -9999 };

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function resizeCanvas() {
  const canvas = canvasEl.value;
  if (!canvas || !context) return;

  deviceScale = Math.min(window.devicePixelRatio || 1, MAX_DEVICE_SCALE);
  width = window.innerWidth;
  height = window.innerHeight;

  canvas.width = Math.round(width * deviceScale);
  canvas.height = Math.round(height * deviceScale);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  context.setTransform(deviceScale, 0, 0, deviceScale, 0, 0);
}

function createParticle() {
  return {
    x: Math.random() * width,
    y: Math.random() * height,
    vx: randomBetween(-0.12, 0.12),
    vy: randomBetween(-0.1, 0.14),
    r: randomBetween(0.6, 1.8),
    a: randomBetween(0.16, 0.46),
    phase: randomBetween(0, Math.PI * 2),
  };
}

function initParticles() {
  const count = Math.min(Math.floor((width * height) / PARTICLE_DENSITY), MAX_PARTICLES);
  particles = Array.from({ length: Math.max(42, count) }, createParticle);
}

function drawAtmosphere(time) {
  const cx = width * 0.52 + Math.sin(time * 0.00025) * 90;
  const cy = height * 0.36 + Math.cos(time * 0.00018) * 60;
  const radius = Math.min(width, height) * 0.42;
  const gradient = context.createRadialGradient(cx, cy, 0, cx, cy, radius);
  gradient.addColorStop(0, "rgba(139, 37, 0, 0.075)");
  gradient.addColorStop(0.38, "rgba(184, 74, 42, 0.032)");
  gradient.addColorStop(1, "rgba(139, 37, 0, 0)");
  context.fillStyle = gradient;
  context.fillRect(0, 0, width, height);

  const cx2 = width * 0.78 + Math.cos(time * 0.00021) * 110;
  const cy2 = height * 0.78 + Math.sin(time * 0.00017) * 70;
  const radius2 = Math.min(width, height) * 0.3;
  const gradient2 = context.createRadialGradient(cx2, cy2, 0, cx2, cy2, radius2);
  gradient2.addColorStop(0, "rgba(28, 23, 16, 0.045)");
  gradient2.addColorStop(1, "rgba(28, 23, 16, 0)");
  context.fillStyle = gradient2;
  context.fillRect(0, 0, width, height);
}

function updateParticle(particle, time) {
  particle.x += particle.vx + Math.sin(time * 0.0004 + particle.phase) * 0.04;
  particle.y += particle.vy + Math.cos(time * 0.00032 + particle.phase) * 0.035;

  const dx = particle.x - pointer.x;
  const dy = particle.y - pointer.y;
  const distance = Math.sqrt(dx * dx + dy * dy);
  if (distance < 150) {
    const force = ((150 - distance) / 150) * 0.045;
    particle.x += dx * force;
    particle.y += dy * force;
  }

  if (particle.x < -20) particle.x = width + 20;
  if (particle.x > width + 20) particle.x = -20;
  if (particle.y < -20) particle.y = height + 20;
  if (particle.y > height + 20) particle.y = -20;
}

function drawLinks() {
  for (let i = 0; i < particles.length; i += 1) {
    for (let j = i + 1; j < particles.length; j += 1) {
      const a = particles[i];
      const b = particles[j];
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      if (distance < LINK_DISTANCE) {
        context.strokeStyle = `rgba(42, 36, 28, ${(1 - distance / LINK_DISTANCE) * 0.075})`;
        context.lineWidth = 0.7;
        context.beginPath();
        context.moveTo(a.x, a.y);
        context.lineTo(b.x, b.y);
        context.stroke();
      }
    }
  }
}

function drawParticles(time) {
  for (const particle of particles) {
    updateParticle(particle, time);
    const alpha = particle.a + Math.sin(time * 0.001 + particle.phase) * 0.08;
    context.fillStyle = `rgba(42, 36, 28, ${Math.max(0.08, alpha)})`;
    context.beginPath();
    context.arc(particle.x, particle.y, particle.r, 0, Math.PI * 2);
    context.fill();
  }
}

function loop(time) {
  context.clearRect(0, 0, width, height);
  drawAtmosphere(time);
  drawLinks();
  drawParticles(time);
  animationFrame = window.requestAnimationFrame(loop);
}

function handleResize() {
  resizeCanvas();
  initParticles();
}

function handlePointerMove(event) {
  pointer = { x: event.clientX, y: event.clientY };
}

function handlePointerLeave() {
  pointer = { x: -9999, y: -9999 };
}

function stop() {
  if (animationFrame) {
    window.cancelAnimationFrame(animationFrame);
    animationFrame = 0;
  }

  window.removeEventListener("resize", handleResize);
  window.removeEventListener("mousemove", handlePointerMove);
  window.removeEventListener("mouseleave", handlePointerLeave);
}

onMounted(() => {
  const canvas = canvasEl.value;
  if (!canvas) return;

  context = canvas.getContext("2d", { alpha: true });
  if (!context) return;

  resizeCanvas();
  initParticles();

  window.addEventListener("resize", handleResize, { passive: true });
  window.addEventListener("mousemove", handlePointerMove, { passive: true });
  window.addEventListener("mouseleave", handlePointerLeave, { passive: true });

  if (prefersReducedMotion()) {
    drawAtmosphere(0);
    drawParticles(0);
    return;
  }

  animationFrame = window.requestAnimationFrame(loop);
});

onBeforeUnmount(() => {
  stop();
});
</script>

<template>
  <canvas ref="canvasEl" class="print-particles" aria-hidden="true"></canvas>
</template>
