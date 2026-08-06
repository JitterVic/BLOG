<script setup>
import { RouterLink } from "vue-router";

defineProps({
  posts: { type: Array, required: true },
});
</script>

<template>
  <section class="related-section print-related-section">
    <div class="sec-hd rv">
      <span class="sec-hd__n">Next</span>
      <h2 class="sec-hd__t">你也许还会想看</h2>
      <div class="sec-hd__line"></div>
    </div>

    <div class="g2e print-related-grid">
      <RouterLink
        v-for="(item, index) in posts"
        :key="item.slug"
        :to="`/posts/${item.slug}`"
        class="art print-article-strip rv"
        :data-reveal-delay="index * 70"
      >
        <span class="section-label">{{ item.category }}</span>
        <h3 class="art__t">{{ item.title }}</h3>
        <p class="art__p">{{ item.excerpt }}</p>
      </RouterLink>
    </div>
  </section>
</template>
