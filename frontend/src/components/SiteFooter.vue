<script setup>
// 页脚（DESIGN.md §4.4）：主栏底部，非 sticky，上方 1px 格线。
// 第一行座右铭（楷体）；第二行版权与「清除读迹」文字按钮。没有刊章、没有版权大块。

import { useReadLog } from "../composables/useReadLog";

const { clearRead } = useReadLog();
const year = new Date().getFullYear();
</script>

<template>
  <footer class="site-footer">
    <p class="site-footer__motto">物格而后知至。</p>
    <p class="site-footer__meta">
      <span>© {{ year }} 至知 Journal</span>
      <button type="button" class="site-footer__clear text-btn" @click="clearRead">清除读迹</button>
    </p>
  </footer>
</template>
