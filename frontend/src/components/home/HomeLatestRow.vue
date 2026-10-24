<script setup>
import { RouterLink } from "vue-router";

import { displayDate } from "../../composables/useFormat";

/**
 * 第 2 版「最近更新」的次要稿件卡：与头条同一套版式（分类行 / 标题 / 摘要 / 元信息），
 * 只是整体缩小一档，因此复用 `.art__cat` / `.art__t` / `.art__p` / `.art__meta`
 * 这四个排版类，再靠 `.home-secondary-card` 做尺度覆盖。
 * 有封面图时在左侧带一枚小图，没有则整卡交给文字，避免留下空槽。
 */
defineProps({
  posts: { type: Array, required: true },
});
</script>

<template>
  <div class="home-latest-row">
    <p class="home-latest-row__caption">本期其余 · Also In This Issue</p>
    <div
      class="home-latest-row__grid"
      :class="{ 'is-single': posts.length === 1 }"
      :style="`--row-cols: ${Math.min(posts.length, 2)}`"
    >
      <RouterLink
        v-for="(post, index) in posts"
        :key="post.slug"
        :to="`/posts/${post.slug}`"
        class="art home-secondary-card rv"
        data-cursor="阅读"
        :data-reveal-delay="160 + index * 70"
      >
        <figure v-if="post.cover_image" class="home-secondary-card__thumb">
          <img
            :src="post.cover_image"
            alt=""
            width="320"
            height="214"
            loading="lazy"
            decoding="async"
            @error="(event) => event.target.closest('figure').classList.add('is-broken')"
          >
        </figure>
        <div class="home-secondary-card__body">
          <div class="home-secondary-card__topline">
            <span class="home-secondary-card__num">{{ String(index + 2).padStart(2, "0") }}</span>
            <span class="home-secondary-card__date">{{ displayDate(post.published_at) }}</span>
          </div>
          <div class="home-secondary-card__copy">
            <h3 class="art__t">{{ post.title }}</h3>
            <p class="art__p">{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
          </div>
          <div class="art__meta">
            <span>{{ post.category || "Article" }}</span>
            <span>{{ post.read_time }}</span>
          </div>
        </div>
      </RouterLink>
    </div>
  </div>
</template>
