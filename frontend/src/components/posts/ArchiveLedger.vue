<script setup>
import { RouterLink } from "vue-router";

import { shortDate } from "../../composables/useFormat";

/**
 * 文章目录的唯一形态：按年份分组的编年索引。
 *
 * 行结构 = 日期 / 标题+摘要 / 时长+标签。摘要不是装饰——像「第一题 两数相加」
 * 这类标题单看无法判断值不值得读，索引行里必须给一句交代。
 * 标题列不再独占整行宽度（原先 930px 的标题列只用到 150–260px），
 * 余下的宽度交给摘要，行才显得填满。
 */
defineProps({
  groups: { type: Array, required: true },
  latestSlug: { type: String, default: "" },
});
</script>

<template>
  <div class="print-year-ledger posts-index">
    <section
      v-for="([year, items], index) in groups"
      :key="year"
      class="archive print-year-block rv"
      :data-reveal-delay="index * 60"
    >
      <div class="archive__year">
        <span>{{ year }}</span>
        <i class="archive__year-rule"></i>
        <strong>{{ items.length }} 篇</strong>
      </div>
      <ul class="archive__list">
        <li
          v-for="post in items"
          :key="post.slug"
          class="archive__li"
          :class="{ 'is-latest': post.slug === latestSlug }"
        >
          <span class="archive__date">{{ shortDate(post.published_at) }}</span>
          <div class="archive__copy">
            <RouterLink :to="`/posts/${post.slug}`" class="archive__title">
              <span v-if="post.slug === latestSlug" class="archive__badge">最新</span>
              {{ post.title }}
            </RouterLink>
            <p class="archive__excerpt">{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
          </div>
          <div class="archive__meta">
            <span class="archive__read">{{ post.read_time }}</span>
            <span class="archive__tags">
              <span v-for="tag in post.tags?.slice(0, 2)" :key="tag" class="tag tag--code">{{ tag }}</span>
            </span>
          </div>
        </li>
      </ul>
      <div v-if="index < groups.length - 1" class="orn">✦</div>
    </section>
  </div>
</template>
