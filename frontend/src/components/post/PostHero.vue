<script setup>
import { RouterLink } from "vue-router";

defineProps({
  post: { type: Object, required: true },
  siteName: { type: String, default: "Personal Blog" },
});
</script>

<template>
  <header class="post-hero print-post-hero">
    <p class="section-label rv">{{ post.category || "Article" }}</p>
    <h1 class="rv" data-reveal-delay="60">{{ post.title }}</h1>
    <p v-if="post.excerpt" class="post-subtitle rv" data-reveal-delay="120">{{ post.excerpt }}</p>

    <div class="post-meta-row rv" data-reveal-delay="160">
      <span>{{ post.published_at || "未设置日期" }}</span>
      <span>{{ post.read_time }}</span>
    </div>

    <figure v-if="post.cover_image" class="post-cover rv" data-reveal-delay="180">
      <img
        :src="post.cover_image"
        :alt="post.title"
        width="1200"
        height="525"
        loading="lazy"
        decoding="async"
        @error="(event) => event.target.closest('figure').classList.add('is-broken')"
      >
    </figure>

    <blockquote v-if="post.hero_quote" class="rv" data-reveal-delay="200">
      {{ post.hero_quote }}
    </blockquote>

    <div
      v-if="post.tags?.length"
      class="post-card-tags detail-tags print-detail-tags rv"
      data-reveal-delay="240"
    >
      <RouterLink
        v-for="tag in post.tags"
        :key="tag"
        :to="{ path: '/posts', query: { q: tag } }"
        class="tag tag--code"
      >
        {{ tag }}
      </RouterLink>
    </div>
  </header>
</template>
