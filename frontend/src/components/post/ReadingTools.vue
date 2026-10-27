<script setup>
// 文章操作（DESIGN.md §5.4）：仅保留「复制链接」，成功后按钮文字变为「已复制」，
// 1.8 秒后恢复，不改变颜色。印刷不带走。纯前端增强，不请求任何接口。

import { onBeforeUnmount, ref } from "vue";

const copied = ref(false);
let copiedTimer = 0;

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
  <div class="reading-tools" role="group" aria-label="文章操作">
    <button
      type="button"
      class="reading-tools__copy text-btn"
      @click="copyLink"
    >
      <span aria-live="polite">{{ copied ? "已复制" : "复制链接" }}</span>
    </button>
  </div>
</template>
