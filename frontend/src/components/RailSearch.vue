<script setup>
// 搜索框（DESIGN.md §6.6）：左栏常驻一份，窄屏移动菜单里同一份。
// 回车跳 /posts?q=；`/` 键聚焦由 App.vue 全局监听（焦点已在输入控件内时不抢）。
// 不做即时下拉。

import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();

const inputRef = ref(null);
// 初值取当前搜索词；后续路由带 q 进来（如文章页点标签）时同步进框
const query = ref(typeof route.query.q === "string" ? route.query.q : "");

watch(
  () => route.query.q,
  (value) => {
    if (document.activeElement !== inputRef.value) {
      query.value = typeof value === "string" ? value : "";
    }
  },
);

function submit() {
  const q = query.value.trim();
  router.push({ name: "posts", query: q ? { q } : {} });
}

defineExpose({
  focus: () => inputRef.value?.focus(),
});
</script>

<template>
  <form class="rail-search" role="search" @submit.prevent="submit">
    <input
      ref="inputRef"
      v-model="query"
      type="search"
      class="rail-search__input"
      placeholder="搜索文章"
      aria-label="搜索文章"
    >
    <span class="rail-search__key" aria-hidden="true">/</span>
  </form>
</template>
