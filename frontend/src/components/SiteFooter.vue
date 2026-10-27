<script setup>
// 页脚（DESIGN.md §4.4）：主栏底部，非 sticky，上方 1px 格线。
// 第一行座右铭（楷体）；第二行版权与「清除读迹」文字按钮（带行内两步确认防误触）。

import { onBeforeUnmount, ref } from "vue";

import { useReadLog } from "../composables/useReadLog";

const { clearRead } = useReadLog();
const year = new Date().getFullYear();

const confirming = ref(false);
let confirmTimer = 0;

function requestClear() {
  confirming.value = true;
  window.clearTimeout(confirmTimer);
  confirmTimer = window.setTimeout(() => {
    confirming.value = false;
  }, 4000);
}

function cancelClear() {
  confirming.value = false;
  window.clearTimeout(confirmTimer);
}

function confirmClear() {
  clearRead();
  cancelClear();
}

onBeforeUnmount(() => window.clearTimeout(confirmTimer));
</script>

<template>
  <footer class="site-footer">
    <p class="site-footer__motto">物格而后知至。</p>
    <p class="site-footer__meta">
      <span>© {{ year }} 至知 Journal</span>
      <span v-if="!confirming" class="site-footer__clear-wrap">
        <button type="button" class="site-footer__clear text-btn" @click="requestClear">清除读迹</button>
      </span>
      <span v-else class="site-footer__confirm" role="group" aria-label="确认清除读迹">
        <span>确定清除读迹？</span>
        <button type="button" class="site-footer__clear text-btn" @click="confirmClear">确认清除</button>
        <button type="button" class="text-btn" @click="cancelClear">取消</button>
      </span>
    </p>
  </footer>
</template>
