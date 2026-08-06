<script setup>
import { RouterLink } from "vue-router";

import { shortDate } from "../../composables/useFormat";

defineProps({
  groups: { type: Array, required: true },
});
</script>

<template>
  <div class="print-year-ledger unified-archive-view">
    <section
      v-for="([year, items], index) in groups"
      :key="year"
      class="archive print-year-block rv"
      :data-reveal-delay="index * 60"
    >
      <div class="archive__year">
        <span>{{ year }}</span>
        <strong>{{ items.length }} 篇</strong>
      </div>
      <ul class="archive__list">
        <li v-for="post in items" :key="post.slug" class="archive__li">
          <span class="archive__date">{{ shortDate(post.published_at) }}</span>
          <RouterLink :to="`/posts/${post.slug}`" class="archive__title">{{ post.title }}</RouterLink>
          <span class="archive__tags">
            <span v-for="tag in post.tags?.slice(0, 2)" :key="tag" class="tag tag--code">{{ tag }}</span>
          </span>
        </li>
      </ul>
      <div v-if="index < groups.length - 1" class="orn">✦</div>
    </section>
  </div>
</template>
