<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";

/**
 * 阅读工具条（文章页顶栏右侧）：
 * - 正文字号三档（偏小 / 标准 / 偏大），写 <html data-reading>，
 *   样式由 post.css 的 html[data-reading] 规则接管；选择持久化到 localStorage；
 * - 复制链接：写剪贴板后按钮变「✓ 已复制」1.8s（剪贴板 API 不可用时走 execCommand 退路）。
 *
 * 纯前端增强：不请求任何接口，不影响文章内容本身。
 */
const SCALE_KEY = "zhizhi-reading-scale";

const scale = ref(""); // "" = 标准，"sm" = 偏小，"lg" = 偏大
const copied = ref(false);
let copiedTimer = 0;

function applyScale(value) {
  scale.value = value;
  const root = document.documentElement;
  if (value) root.dataset.reading = value;
  else delete root.dataset.reading;
  try {
    if (value) localStorage.setItem(SCALE_KEY, value);
    else localStorage.removeItem(SCALE_KEY);
  } catch {
    // 隐私模式等场景下 localStorage 不可用：本次会话内生效即可
  }
}

onMounted(() => {
  try {
    const saved = localStorage.getItem(SCALE_KEY);
    if (saved === "sm" || saved === "lg") applyScale(saved);
  } catch {
    // 同上，读不到偏好就保持标准字号
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
        :class="{ active: scale === 'sm' }"
        :aria-pressed="scale === 'sm'"
        title="偏小字号"
        @click="applyScale(scale === 'sm' ? '' : 'sm')"
      >A−</button>
      <button
        type="button"
        class="reading-tools__btn"
        :class="{ active: scale === '' }"
        :aria-pressed="scale === ''"
        title="标准字号"
        @click="applyScale('')"
      >A</button>
      <button
        type="button"
        class="reading-tools__btn"
        :class="{ active: scale === 'lg' }"
        :aria-pressed="scale === 'lg'"
        title="偏大字号"
        @click="applyScale(scale === 'lg' ? '' : 'lg')"
      >A+</button>
    </span>
    <button
      type="button"
      class="reading-tools__copy"
      :class="{ 'is-copied': copied }"
      @click="copyLink"
    >
      <span aria-live="polite">{{ copied ? "✓ 已复制" : "复制链接" }}</span>
    </button>
  </div>
</template>
