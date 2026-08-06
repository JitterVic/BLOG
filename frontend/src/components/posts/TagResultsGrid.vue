<script setup>
import { RouterLink } from "vue-router";

import { displayDate } from "../../composables/useFormat";

defineProps({
  tags: { type: Array, required: true },
  selectedTag: { type: String, default: "全部" },
  posts: { type: Array, required: true },
});

defineEmits(["select-tag"]);
</script>

<template>
  <div class="unified-tags-view">
    <aside class="tag-filter-row print-tag-cloud rv" aria-label="标签筛选">
      <button
        v-for="tag in tags"
        :key="tag"
        type="button"
        class="tag-filter-button tag"
        :class="{ active: selectedTag === tag, 'tag--hot': selectedTag === tag }"
        @click="$emit('select-tag', tag)"
      >
        {{ tag }}
      </button>
    </aside>

    <div class="g2e print-tag-results">
      <RouterLink
        v-for="(post, index) in posts"
        :key="post.slug"
        :to="`/posts/${post.slug}`"
        class="art print-article-strip rv"
        :data-reveal-delay="Math.min(index, 6) * 50"
      >
        <div class="art__cat">{{ post.category || "Article" }}</div>
        <h2 class="art__t art__t--lg">{{ post.title }}</h2>
        <p class="art__p">{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
        <div class="art__meta">
          <span>{{ displayDate(post.published_at) }}</span>
          <span>{{ post.read_time }}</span>
        </div>
      </RouterLink>
    </div>
  </div>
</template>
