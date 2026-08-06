<script setup>
defineProps({
  items: { type: Array, required: true },
  activeId: { type: String, default: "" },
});

defineEmits(["navigate"]);
</script>

<template>
  <aside class="article-toc rv" data-reveal-delay="100">
    <div class="article-toc__head">
      <span>On this page</span>
      <strong>{{ String(items.length).padStart(2, "0") }}</strong>
    </div>
    <nav aria-label="文章目录">
      <button
        v-for="(item, index) in items"
        :key="item.id"
        type="button"
        :class="{ active: activeId === item.id, 'is-subsection': item.level === 3 }"
        :aria-current="activeId === item.id ? 'location' : undefined"
        @click="$emit('navigate', item.id)"
      >
        <span>{{ String(index + 1).padStart(2, "0") }}</span>
        <em>{{ item.label }}</em>
      </button>
    </nav>
    <p>阅读时，目录会跟随当前章节。</p>
  </aside>
</template>
