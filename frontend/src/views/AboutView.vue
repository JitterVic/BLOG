<script setup>
import { computed, onMounted } from "vue";

import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";

const { site, ensureSite, error } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });

const introParagraphs = computed(() => {
  const paragraphs = site.value?.about_intro || [];
  if (paragraphs.length) return paragraphs;
  return [
    "至知是一份持续更新的个人博客，用来整理技术实践、项目复盘、阅读笔记和那些值得反复回看的问题。",
    "这里不追求把信息堆满，而是尽量把每次学习和开发留下的判断、取舍与方法写清楚。",
  ];
});
const contactLinks = computed(() => site.value?.social_links || []);

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // The UI already renders a friendlier message via error.
  }
  refreshReveal();
});
</script>

<template>
  <div class="content-view print-subpage quiet-about-page">
    <section class="print-page print-section quiet-about-issue">
      <div class="sec-hd rv">
        <span class="sec-hd__n">03</span>
        <h1 class="sec-hd__t">关于 About</h1>
        <div class="sec-hd__line"></div>
      </div>

      <p v-if="error" class="feedback print-feedback rv">{{ error }}</p>

      <p class="about-chapter-label rv">Editor's Edition</p>
      <div class="quiet-about-layout">
        <article class="quiet-about-card quiet-about-card--intro rv" data-reveal-delay="40">
          <p class="section-label">Editor’s Note</p>
          <h2>关于这本博客</h2>
          <div class="quiet-about-copy">
            <p v-for="paragraph in introParagraphs" :key="paragraph">{{ paragraph }}</p>
          </div>
        </article>

        <aside class="quiet-about-card quiet-about-card--contact rv" data-reveal-delay="120">
          <p class="section-label">Contact</p>
          <h2 class="about-contact-title">如果你想交流</h2>
          <p>欢迎带着上下文、问题或想法来找我。最好的交流，通常始于一个具体而真诚的问题。</p>

          <div v-if="contactLinks.length" class="quiet-contact-list">
            <a
              v-for="item in contactLinks"
              :key="item.label"
              :href="item.url"
              target="_blank"
              rel="noreferrer"
            >
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </a>
          </div>
          <p v-else class="feedback quiet-contact-empty">暂未配置联系方式。</p>
        </aside>
      </div>

      <span class="pg pg--r">— About —</span>
    </section>
  </div>
</template>
