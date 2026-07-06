<script setup>
import { computed } from "vue";
import { RouterLink } from "vue-router";

const props = defineProps({
  post: {
    type: Object,
    required: true,
  },
});

const toneClass = computed(() => `tone-${props.post.tone || "amber"}`);
</script>

<template>
  <article class="post-card paper-card" :class="toneClass">
    <div class="post-card-meta">
      <span>{{ post.category }}</span>
      <span>{{ post.published_at }}</span>
    </div>

    <div class="post-card-body">
      <h3>{{ post.title }}</h3>
      <p>{{ post.excerpt }}</p>
    </div>

    <div class="post-card-tags">
      <span v-for="tag in post.tags" :key="tag">{{ tag }}</span>
    </div>

    <div class="post-card-footer">
      <span>{{ post.read_time }}</span>
      <RouterLink :to="`/posts/${post.slug}`">阅读全文</RouterLink>
    </div>
  </article>
</template>

