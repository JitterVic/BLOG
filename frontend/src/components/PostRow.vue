<script setup>
// Row 列表行（DESIGN.md §6.1）：首页、列表页、相关推荐、榜单共用。
// 整行可点（标题链接 ::after 拉满整行，tab 停靠点仍只有标题）；
// 已读 → 标题套荧光笔 + 视觉隐藏「已读」；搜索命中 → 标题与摘要中标亮。

import { computed } from "vue";
import { RouterLink } from "vue-router";

import { useReadLog } from "../composables/useReadLog";
import { readTimeLabel, shortDate } from "../composables/useFormat";
import { useTitleMorph } from "../composables/useTitleMorph";

const props = defineProps({
  post: { type: Object, required: true },
  /** 日期格式：full = YYYY-MM-DD（首页），short = MM-DD（列表页年分组内） */
  dateFormat: { type: String, default: "short" },
  /** 搜索命中词：给标题与摘要的匹配段套荧光笔（§6.6） */
  highlight: { type: String, default: "" },
});

const { isRead } = useReadLog();
const { handleOpen } = useTitleMorph();

const isReadState = computed(() => isRead(props.post?.slug));

const dateText = computed(() => {
  const raw = props.post?.published_at || "";
  return props.dateFormat === "full" ? raw : shortDate(raw);
});

const timeText = computed(() => readTimeLabel(props.post?.read_time));

/** 命中词分段（大小写不敏感）；不做 v-html，直接文本拼接。 */
function segments(text) {
  const value = String(text || "");
  const needle = props.highlight.trim().toLowerCase();
  if (!needle || !value) return [{ text: value, mark: false }];
  const lower = value.toLowerCase();
  const parts = [];
  let cursor = 0;
  let index = lower.indexOf(needle);
  while (index !== -1) {
    if (index > cursor) parts.push({ text: value.slice(cursor, index), mark: false });
    parts.push({ text: value.slice(index, index + needle.length), mark: true });
    cursor = index + needle.length;
    index = lower.indexOf(needle, cursor);
  }
  if (cursor < value.length) parts.push({ text: value.slice(cursor), mark: false });
  return parts;
}
</script>

<template>
  <article class="post-row">
    <p v-if="dateText" class="post-row__date">{{ dateText }}</p>
    <div class="post-row__main">
      <h3 class="post-row__title">
        <RouterLink
          class="post-row__link"
          :class="{ 'marker': isReadState }"
          :to="{ name: 'post', params: { slug: post.slug } }"
          @click="handleOpen($event, { name: 'post', params: { slug: post.slug } })"
        >
          <template v-if="highlight">
            <template v-for="(seg, i) in segments(post.title)" :key="i">
              <mark v-if="seg.mark" class="marker">{{ seg.text }}</mark>
              <template v-else>{{ seg.text }}</template>
            </template>
          </template>
          <template v-else>{{ post.title }}</template>
        </RouterLink>
        <span v-if="isReadState" class="sr-only">（已读）</span>
      </h3>
      <p v-if="post.excerpt" class="post-row__excerpt">
        <template v-if="highlight">
          <template v-for="(seg, i) in segments(post.excerpt)" :key="i">
            <mark v-if="seg.mark" class="marker">{{ seg.text }}</mark>
            <template v-else>{{ seg.text }}</template>
          </template>
        </template>
        <template v-else>{{ post.excerpt }}</template>
      </p>
    </div>
    <div class="post-row__meta">
      <span v-if="post.category">{{ post.category }}</span>
      <span v-if="timeText">{{ timeText }}</span>
    </div>
  </article>
</template>
