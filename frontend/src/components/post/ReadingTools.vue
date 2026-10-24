<script setup>
// 阅读工具（DESIGN.md §5.3）：正文字号三档（写 html[data-reading]，只作用于 .prose，
// 行高保持 2），持久化键 zhizhi:reading；「复制链接」成功后按钮文字变为「已复制」，
// 1.8 秒后恢复，不改变颜色。印刷不带走。纯前端增强，不请求任何接口。

import { onBeforeUnmount, onMounted, ref } from "vue";

const STORAGE_KEY = "zhizhi:reading";

const scale = ref(""); // "" = 标准，"sm" = 偏小，"lg" = 偏大
const copied = ref(false);
let copiedTimer = 0;

function applyScale(value) {
  scale.value = value;
  const root = document.documentElement;
  if (value) root.dataset.reading = value;
  else delete root.dataset.reading;
  try {
    if (value) localStorage.setItem(STORAGE_KEY, value);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // 隐私模式等场景下 localStorage 不可用：本次会话内生效即可
  }
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "sm" || saved === "lg") applyScale(saved);
  } catch {
    // 读不到偏好就保持标准字号
  }
});

async function copyLink() {
  const url = window.location.href;
  try {
    await navigator.clipboard.writeText(url);
  } catch {
    const textarea = document.createElement("textarea");
    textarea.value = url;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    try {
      document.execCommand("copy");
    } catch {
      // 退路也失败时保持按钮原样，不伪造成功态
      return;
    } finally {
      textarea.remove();
    }
  }
  copied.value = true;
  window.clearTimeout(copiedTimer);
  copiedTimer = window.setTimeout(() => {
    copied.value = false;
  }, 1800);
}

onBeforeUnmount(() => window.clearTimeout(copiedTimer));
</script>

<template>
  <div class="reading-tools" role="group" aria-label="阅读设置">
    <span class="reading-tools__group" role="group" aria-label="正文字号">
      <button
        type="button"
        class="reading-tools__btn"
        :class="{ 'is-active': scale === 'sm' }"
        :aria-pressed="scale === 'sm'"
        title="偏小字号"
        @click="applyScale(scale === 'sm' ? '' : 'sm')"
      >A−</button>
      <button
        type="button"
        class="reading-tools__btn"
        :class="{ 'is-active': scale === '' }"
        :aria-pressed="scale === ''"
        title="标准字号"
        @click="applyScale('')"
      >A</button>
      <button
        type="button"
        class="reading-tools__btn"
        :class="{ 'is-active': scale === 'lg' }"
        :aria-pressed="scale === 'lg'"
        title="偏大字号"
        @click="applyScale(scale === 'lg' ? '' : 'lg')"
      >A+</button>
    </span>
    <button
      type="button"
      class="reading-tools__copy text-btn"
      @click="copyLink"
    >
      <span aria-live="polite">{{ copied ? "已复制" : "复制链接" }}</span>
    </button>
  </div>
</template>
