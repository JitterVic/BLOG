<script setup>
/**
 * 目录页的筛选工具条：左侧栏目（大类）、右侧搜索。
 *
 * 栏目来自站点载荷里「已发布文章实际用到的分类」，而不是标签——标签会随着写作
 * 无限生长，做成筛选条迟早会变成一屏胶囊按钮；栏目是编辑层面少数几个固定选择，
 * 才撑得住长期整洁。细粒度信息交给标签（只展示）与关键词（只检索）。
 */
defineProps({
  categories: { type: Array, required: true },
  selectedCategory: { type: String, default: "全部" },
  total: { type: Number, default: 0 },
  searchQuery: { type: String, default: "" },
});

defineEmits(["set-category", "update:searchQuery", "clear-search"]);
</script>

<template>
  <div class="article-toolbox rv">
    <div class="article-cat-filter" role="group" aria-label="按栏目筛选">
      <button
        type="button"
        class="cat-filter-button"
        :class="{ active: selectedCategory === '全部' }"
        :aria-pressed="selectedCategory === '全部'"
        @click="$emit('set-category', '全部')"
      >
        全部
      </button>
      <button
        v-for="item in categories"
        :key="item.name"
        type="button"
        class="cat-filter-button"
        :class="{ active: selectedCategory === item.name }"
        :aria-pressed="selectedCategory === item.name"
        @click="$emit('set-category', item.name)"
      >
        {{ item.name }}<span class="cat-filter-button__count">{{ item.count }}</span>
      </button>
    </div>

    <label class="article-search">
      <span class="article-search__field">
        <input
          :value="searchQuery"
          type="search"
          placeholder="搜索标题、摘要、标签或关键词"
          autocomplete="off"
          :aria-label="`搜索 ${total} 篇文章`"
          @input="$emit('update:searchQuery', $event.target.value)"
        >
        <button
          v-if="searchQuery"
          type="button"
          aria-label="清除搜索关键词"
          @click="$emit('clear-search')"
        >清除</button>
      </span>
    </label>
  </div>
</template>
