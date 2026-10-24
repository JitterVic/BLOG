<script setup>
// 404（DESIGN.md §5.5）：h1 + 一句说明 + 两个文字链接。
// 不做插画、不做动画。

import { RouterLink } from "vue-router";
</script>

<template>
  <div class="nf-view">
    <h1>找不到这一页</h1>
    <p>这个地址下没有内容。链接可能写错了，或文章已被移走。</p>
    <p class="nf-view__actions">
      <RouterLink class="text-link" to="/">回首页</RouterLink>
      <RouterLink class="text-link" to="/posts">全部文章</RouterLink>
    </p>
  </div>
</template>
