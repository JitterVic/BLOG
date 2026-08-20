<script setup>
defineProps({
  loading: Boolean,
  error: { type: String, default: "" },
  empty: Boolean,
  variant: { type: String, default: "generic" }, // "generic" | "post" | "posts" | "home"
  loadingMessage: { type: String, default: "正在排版装订……" },
  emptyMessage: { type: String, default: "暂无收录内容。" },
  emptyTitle: { type: String, default: "版面留白" },
  retryLabel: { type: String, default: "重新装订" },
});

defineEmits(["retry"]);
</script>

<template>
  <!-- Loading: 报刊骨架屏 -->
  <div
    v-if="loading"
    class="editorial-skeleton"
    :class="`editorial-skeleton--${variant}`"
    aria-busy="true"
    aria-label="内容正在加载"
  >
    <!-- Post Detail Skeleton -->
    <div v-if="variant === 'post'" class="sk-post-wrap">
      <div class="sk-line sk-line--subtle sk-w-30"></div>
      <div class="sk-line sk-line--title sk-w-85"></div>
      <div class="sk-line sk-line--title sk-w-60"></div>
      <div class="sk-meta-bar">
        <div class="sk-badge"></div>
        <div class="sk-line sk-w-20"></div>
        <div class="sk-line sk-w-20"></div>
      </div>
      <div class="sk-divider"></div>
      <div class="sk-article-grid">
        <div class="sk-toc-aside">
          <div class="sk-line sk-w-50"></div>
          <div class="sk-line sk-w-80"></div>
          <div class="sk-line sk-w-70"></div>
          <div class="sk-line sk-w-85"></div>
        </div>
        <div class="sk-body-flow">
          <div class="sk-line sk-w-100"></div>
          <div class="sk-line sk-w-95"></div>
          <div class="sk-line sk-w-90"></div>
          <div class="sk-line sk-w-75"></div>
          <div class="sk-block sk-block--code"></div>
          <div class="sk-line sk-w-100"></div>
          <div class="sk-line sk-w-92"></div>
        </div>
      </div>
    </div>

    <!-- Posts Catalog Skeleton -->
    <div v-else-if="variant === 'posts'" class="sk-posts-wrap">
      <div class="sk-toolbar-bar">
        <div class="sk-tabs">
          <div class="sk-tab"></div>
          <div class="sk-tab"></div>
          <div class="sk-tab"></div>
        </div>
        <div class="sk-search-input"></div>
      </div>
      <div class="sk-cards-grid">
        <div v-for="i in 4" :key="i" class="sk-card">
          <div class="sk-line sk-line--subtle sk-w-25"></div>
          <div class="sk-line sk-line--title sk-w-75"></div>
          <div class="sk-line sk-w-100"></div>
          <div class="sk-line sk-w-65"></div>
          <div class="sk-tag-row">
            <div class="sk-badge"></div>
            <div class="sk-badge"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Generic Skeleton & Shimmer Bar -->
    <div v-else class="sk-generic-wrap">
      <div class="sk-line sk-line--title sk-w-50"></div>
      <div class="sk-line sk-w-85"></div>
      <div class="sk-line sk-w-70"></div>
      <div class="sk-line sk-w-40"></div>
      <span class="sk-loading-caption">{{ loadingMessage }}</span>
    </div>
  </div>

  <!-- Error / Empty 状态卡片 -->
  <section
    v-else-if="error || empty"
    class="async-state print-feedback editorial-state-card"
    :class="{ 'async-state--error': error, 'async-state--empty': empty && !error }"
    :role="error ? 'alert' : 'status'"
    aria-live="polite"
  >
    <div class="state-card-stamp">
      <span>{{ error ? "FAIL" : "EMPTY" }}</span>
    </div>
    <span class="async-state__eyebrow">
      {{ error ? "Editorial Notice · 异常报告" : "Edition Archive · 留白记录" }}
    </span>
    <strong class="state-card-title">{{ error ? "版面装订受阻" : emptyTitle }}</strong>
    <p class="state-card-desc">{{ error || emptyMessage }}</p>
    <div v-if="error" class="state-card-actions">
      <button type="button" class="cover-button primary-link" @click="$emit('retry')">
        {{ retryLabel }}
      </button>
    </div>
  </section>
</template>
