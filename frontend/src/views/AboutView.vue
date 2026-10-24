<script setup>
// 关于页（DESIGN.md §5.4）：主栏 --col-read 宽，开头一段楷体，其后正文。
// 联系方式用 <dl>；不使用卡片。

import { computed, onMounted } from "vue";

import AsyncState from "../components/AsyncState.vue";
import { useSite } from "../composables/useSite";

const { site, ensureSite, loading, error } = useSite();

const introParagraphs = computed(() => {
  const paragraphs = site.value?.about_intro || [];
  if (paragraphs.length) return paragraphs;
  return [
    "至知是一份持续更新的个人博客，用来整理技术实践、项目复盘、阅读笔记和那些值得反复回看的问题。",
  ];
});
const contactLinks = computed(() => site.value?.social_links || []);

async function retrySite() {
  try {
    await ensureSite({ force: true });
  } catch (err) {
    // 错误态仍由 AsyncState 呈现
  }
}

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // 错误态由 AsyncState 呈现
  }
});
</script>

<template>
  <div class="about-view">
    <AsyncState
      v-if="loading && !site"
      loading
      loading-message="正在加载…"
    />
    <AsyncState
      v-else-if="error && !site"
      :error="error"
      empty-message="请检查网络后重试。"
      @retry="retrySite"
    />

    <template v-else>
      <h1>关于</h1>

      <div class="about-lead">
        <p v-for="paragraph in introParagraphs" :key="paragraph">{{ paragraph }}</p>
      </div>

      <section class="prose">
        <p v-if="site?.summary">{{ site.summary }}</p>
      </section>

      <dl v-if="contactLinks.length" class="about-contact">
        <template v-for="item in contactLinks" :key="item.label">
          <dt>{{ item.label }}</dt>
          <dd>
            <a class="text-link" :href="item.url" target="_blank" rel="noreferrer">{{ item.value }}</a>
          </dd>
        </template>
      </dl>
    </template>
  </div>
</template>
