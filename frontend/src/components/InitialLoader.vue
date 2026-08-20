<script setup>
import { onMounted, ref } from "vue";

const isVisible = ref(true);
const isMounted = ref(false);

const emit = defineEmits(["ready"]);

onMounted(() => {
  isMounted.value = true;
  // Natural brief presentation (800ms) for high-end editorial feel
  window.setTimeout(() => {
    isVisible.value = false;
    emit("ready");
  }, 850);
});
</script>

<template>
  <Transition name="journal-loader">
    <div v-if="isVisible" class="journal-initial-loader" aria-hidden="true">
      <div class="loader-content" :class="{ 'is-active': isMounted }">
        <div class="loader-masthead">
          <span>VOL. 03 · DIGITAL EDITION</span>
          <span class="loader-dot">·</span>
          <span>EST. 2026</span>
        </div>

        <h1 class="loader-title">
          至知 <em>Journal</em>
        </h1>

        <div class="loader-ink-bar">
          <div class="loader-ink-fill"></div>
        </div>

        <div class="loader-caption">
          <span class="loader-spinner"></span>
          <span>正在排版装订内容……</span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.journal-initial-loader {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: grid;
  place-items: center;
  background: var(--paper, #f6f1e8);
  color: var(--ink, #1c1710);
  pointer-events: all;
  overflow: hidden;
}

.journal-initial-loader::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle, rgba(42, 36, 28, 0.14) 0.5px, transparent 0.6px),
    linear-gradient(90deg, rgba(42, 36, 28, 0.015), transparent 50%, rgba(255, 255, 255, 0.025));
  background-size: 4px 4px, 100% 100%;
  opacity: 0.22;
  mix-blend-mode: multiply;
  pointer-events: none;
}

.loader-content {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 2rem;
  opacity: 0;
  transform: translate3d(0, 16px, 0);
  transition:
    opacity 0.45s var(--ease-quart, cubic-bezier(0.25, 1, 0.5, 1)),
    transform 0.55s var(--ease-expo, cubic-bezier(0.16, 1, 0.3, 1));
}

.loader-content.is-active {
  opacity: 1;
  transform: translate3d(0, 0, 0);
}

.loader-masthead {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-family: var(--f-mono, monospace);
  font-size: 0.58rem;
  font-weight: 600;
  letter-spacing: 0.22em;
  color: var(--accent, #8b2500);
  text-transform: uppercase;
  margin-bottom: 0.6rem;
}

.loader-dot {
  opacity: 0.5;
}

.loader-title {
  margin: 0 0 1.2rem;
  font-family: var(--f-display, "Playfair Display", serif);
  font-size: clamp(2.4rem, 6vw, 3.8rem);
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: var(--ink, #1c1710);
}

.loader-title em {
  font-style: italic;
  font-weight: 400;
  color: var(--ink-light, #5e5548);
}

.loader-ink-bar {
  position: relative;
  width: min(240px, 60vw);
  height: 2px;
  background: rgba(42, 36, 28, 0.12);
  margin-bottom: 1.2rem;
  overflow: hidden;
  border-radius: 1px;
}

.loader-ink-fill {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, var(--accent, #8b2500), var(--accent-light, #b84a2a));
  transform-origin: left center;
  animation: loader-ink-expand 0.75s var(--ease-quart, cubic-bezier(0.25, 1, 0.5, 1)) forwards;
}

@keyframes loader-ink-expand {
  0% { transform: scaleX(0); }
  100% { transform: scaleX(1); }
}

.loader-caption {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  font-family: var(--f-mono, monospace);
  font-size: 0.62rem;
  letter-spacing: 0.12em;
  color: var(--ink-faded, #8a7f6f);
}

.loader-spinner {
  width: 10px;
  height: 10px;
  border: 1.5px solid rgba(139, 37, 0, 0.25);
  border-top-color: var(--accent, #8b2500);
  border-radius: 50%;
  animation: loader-spin 0.8s linear infinite;
}

@keyframes loader-spin {
  to { transform: rotate(360deg); }
}

/* Exit Transition */
.journal-loader-leave-active {
  transition:
    opacity 0.42s var(--ease-quart, cubic-bezier(0.25, 1, 0.5, 1)),
    transform 0.5s var(--ease-expo, cubic-bezier(0.16, 1, 0.3, 1));
}

.journal-loader-leave-to {
  opacity: 0;
  transform: translate3d(0, -100%, 0);
}
</style>
