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
  /**
   * 局部状态用轻量提示：不盖 FAIL 印章、不撑整版高度。
   * 用在「加载更多失败」这类只影响一段内容的场合——整版重卡会让人以为整页都废了。
   */
  compact: Boolean,
});

defineEmits(["retry"]);
</script>

<template>
  <!-- Loading: 报刊骨架屏 -->
  <div
    v-if="loading"
    class="editorial-skeleton"
    :class="`editorial-skeleton--${variant}`"
    role="status"
    aria-live="polite"
    aria-busy="true"
  >
    <span class="sr-only">{{ loadingMessage }}</span>

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

    <!-- Posts Catalog Skeleton：形状必须与 ArchiveLedger 一致（工具栏 + 年份 + 索引细行），
         否则加载完成时整版从卡片网格跳成编年索引，读者会以为换了一页。 -->
    <div v-else-if="variant === 'posts'" class="sk-posts-wrap">
      <div class="sk-toolbar-bar">
        <div class="sk-tabs">
          <div class="sk-tab"></div>
          <div class="sk-tab"></div>
          <div class="sk-tab"></div>
        </div>
        <div class="sk-search-input"></div>
      </div>
      <div class="sk-ledger">
        <div class="sk-ledger__year">
          <div class="sk-line sk-line--year"></div>
          <div class="sk-line sk-w-20"></div>
        </div>
        <div v-for="i in 5" :key="`r-${i}`" class="sk-ledger__row">
          <div class="sk-line sk-line--date"></div>
          <div class="sk-ledger__copy">
            <div class="sk-line sk-line--title sk-w-70"></div>
            <div class="sk-line sk-w-95"></div>
          </div>
          <div class="sk-line sk-line--rowmeta"></div>
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

  <!-- Error / Empty 状态卡片。
       语义分工：错误是 alert（打断式播报一次），空状态是 status（礼貌播报）。
       此前两者同时挂着 role="alert" 与 aria-live="polite"，互相打架。 -->
  <section
    v-else-if="error || empty"
    class="async-state print-feedback editorial-state-card"
    :class="{
      'async-state--error': error,
      'async-state--empty': empty && !error,
      'async-state--compact': compact,
    }"
    :role="error ? 'alert' : 'status'"
    :aria-live="error ? undefined : 'polite'"
  >
    <div v-if="!compact" class="state-card-stamp">
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
