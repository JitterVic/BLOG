<script setup>
// 读迹 ReadTrace（DESIGN.md §6.3）：仅本机统计已读篇数，只输出计数文案，
// 不再渲染「正」字描红图形（v2.1 减法收口）。已读标记见各列表标题的 .marker。

import { useReadLog } from "../composables/useReadLog";

const { readable, readCount, totalCount, ensureCatalog } = useReadLog();
ensureCatalog();
</script>

<template>
  <div v-if="readable && totalCount" class="read-trace">
    <p class="read-trace__meta">已读 {{ readCount }} / 共 {{ totalCount }} 篇</p>
  </div>
</template>
