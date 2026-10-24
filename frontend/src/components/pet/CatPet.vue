<script setup>
// 桌宠（DESIGN.md §6.8）：仅在 pointer: fine 且 ≥ 1100px 时出现。
// 默认静止（睡姿），只响应点击（点一下醒 1.6 秒再睡回去）；不追光标、不拖拽、无音效。
// 关闭开关持久化键 zhizhi:cat；prefers-reduced-motion 下同样为静态图（无过渡）。

import { computed, onBeforeUnmount, ref } from "vue";

import { useMediaQuery } from "../../composables/useMediaQuery";

import pettingHearts from "../../assets/pet/petting_hearts.png";
import sleepingCurl from "../../assets/pet/sleeping_curl.png";

const STORAGE_KEY = "zhizhi:cat";

const finePointer = useMediaQuery("(pointer: fine)");
const wideViewport = useMediaQuery("(min-width: 1100px)");

function readEnabled() {
  try {
    return localStorage.getItem(STORAGE_KEY) !== "off";
  } catch {
    return true;
  }
}

const enabled = ref(readEnabled());
const petted = ref(false);
let pettedTimer = 0;

const visible = computed(() => enabled.value && finePointer.value && wideViewport.value);

function handlePetClick() {
  if (petted.value) return;
  petted.value = true;
  window.clearTimeout(pettedTimer);
  pettedTimer = window.setTimeout(() => {
    petted.value = false;
  }, 1600);
}

function disable() {
  enabled.value = false;
  try {
    localStorage.setItem(STORAGE_KEY, "off");
  } catch {
    // localStorage 不可用时仅本次会话生效
  }
}

onBeforeUnmount(() => window.clearTimeout(pettedTimer));
</script>

<template>
  <div v-if="visible" class="cat-pet">
    <button
      type="button"
      class="cat-pet__sprite"
      aria-label="博客吉祥物猫咪：点击会有反应"
      @click="handlePetClick"
    >
      <img :src="petted ? pettingHearts : sleepingCurl" alt="" width="72" height="72">
    </button>
    <button type="button" class="cat-pet__close" aria-label="关闭桌宠" @click="disable">×</button>
  </div>
</template>

<style scoped>
.cat-pet {
  position: fixed;
  right: var(--gutter);
  bottom: var(--sp-4);
  z-index: 30; /* 低于顶栏（40）与对话框（top-layer 恒在其上） */
  width: 72px;
}

.cat-pet__sprite {
  display: block;
  padding: 0;
  background: none;
  border: 0;
  border-radius: 50%;
  cursor: pointer;
}

.cat-pet__sprite img {
  width: 72px;
  height: 72px;
  object-fit: contain;
  transition: opacity var(--t-1) var(--ease);
}

.cat-pet__close {
  position: absolute;
  top: -4px;
  right: -4px;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  padding: 0;
  font-size: 0.8125rem;
  line-height: 1;
  color: var(--ink-soft);
  background: var(--paper);
  border: 1px solid var(--line-ui);
  border-radius: 50%;
  opacity: 0;
  transition: opacity var(--t-1) var(--ease);
}

.cat-pet:hover .cat-pet__close,
.cat-pet__close:focus-visible {
  opacity: 1;
}

@media (prefers-reduced-motion: reduce) {
  .cat-pet__sprite img,
  .cat-pet__close {
    transition: none;
  }
}
</style>
