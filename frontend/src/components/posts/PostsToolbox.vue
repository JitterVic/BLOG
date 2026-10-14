<script setup>
/**
 * 目录页的筛选工具条：左侧标签筛选、右侧搜索。
 *
 * 原先这里是「最新 / 归档 / 标签」三视图切换器。三套视图装的是同一批文章、
 * 只是排布不同，读者要先做一次与内容无关的选择；现在目录只剩编年索引一种形态，
 * 切换器随之取消，标签从「一个视图」降格为「一个筛选条件」。
 */
defineProps({
  tags: { type: Array, required: true },
  selectedTag: { type: String, default: "全部" },
  searchQuery: { type: String, default: "" },
});

defineEmits(["set-tag", "update:searchQuery", "clear-search"]);
</script>

<template>
  <div class="article-toolbox rv">
    <div class="article-tag-filter" role="group" aria-label="按标签筛选">
      <button
        v-for="tag in tags"
        :key="tag"
        type="button"
        class="tag-filter-button tag"
        :class="{ active: selectedTag === tag, 'tag--hot': selectedTag === tag }"
        :aria-pressed="selectedTag === tag"
        @click="$emit('set-tag', tag)"
      >
        {{ tag }}
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
