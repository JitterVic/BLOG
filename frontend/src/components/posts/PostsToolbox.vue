<script setup>
defineProps({
  viewOptions: { type: Array, required: true },
  activeView: { type: String, required: true },
  searchQuery: { type: String, default: "" },
});

defineEmits(["set-view", "update:searchQuery", "clear-search"]);
</script>

<template>
  <div class="article-toolbox rv">
    <div class="article-view-switch" role="tablist" aria-label="文章目录视图">
      <button
        v-for="item in viewOptions"
        :key="item.id"
        type="button"
        class="article-view-button"
        :class="{ active: activeView === item.id }"
        role="tab"
        :aria-selected="activeView === item.id"
        @click="$emit('set-view', item.id)"
      >
        <strong>{{ item.label }}</strong>
        <span>{{ item.english }}</span>
      </button>
    </div>

    <label class="article-search">
      <span class="article-search__label">Search the issue</span>
      <span class="article-search__field">
        <input
          :value="searchQuery"
          type="search"
          placeholder="搜索标题、摘要或标签"
          autocomplete="off"
          @input="$emit('update:searchQuery', $event.target.value)"
        >
        <button v-if="searchQuery" type="button" @click="$emit('clear-search')">清除</button>
      </span>
    </label>
  </div>
</template>
