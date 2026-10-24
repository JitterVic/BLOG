<script setup>
// 状态与骨架（DESIGN.md §6.7）：骨架屏与真实版面同构，静态灰条、不做流光。
// 错误是 alert（打断式播报一次），空状态是 status（礼貌播报）。
// 文案说清发生了什么、怎么办；错误不道歉、不含糊。

defineProps({
  loading: Boolean,
  error: { type: String, default: "" },
  empty: Boolean,
  /** 骨架形状：rows = 列表行；feature = 首页最新一篇；post = 文章头 + 正文行 */
  variant: { type: String, default: "generic" },
  loadingMessage: { type: String, default: "正在加载…" },
  emptyMessage: { type: String, default: "还没有内容。" },
  retryLabel: { type: String, default: "重试" },
  compact: Boolean,
});

defineEmits(["retry"]);
</script>

<template>
  <div
    v-if="loading"
    class="sk"
    :class="`sk--${variant}`"
    role="status"
    aria-live="polite"
    aria-busy="true"
  >
    <span class="sr-only">{{ loadingMessage }}</span>

    <template v-if="variant === 'rows'">
      <div v-for="i in 5" :key="i" class="sk-row-unit">
        <div class="sk-bar sk-bar--date"></div>
        <div class="sk-row-copy">
          <div class="sk-bar sk-bar--title" :style="{ width: `${58 + (i * 7) % 30}%` }"></div>
          <div class="sk-bar sk-bar--w70"></div>
        </div>
        <div class="sk-bar sk-bar--meta"></div>
      </div>
    </template>

    <template v-else-if="variant === 'feature'">
      <div class="sk-bar sk-bar--w40"></div>
      <div class="sk-bar sk-bar--title"></div>
      <div class="sk-bar sk-bar--w70"></div>
      <div class="sk-bar sk-bar--w30"></div>
    </template>

    <template v-else-if="variant === 'post'">
      <div class="sk-bar sk-bar--w20"></div>
      <div class="sk-bar sk-bar--title"></div>
      <div class="sk-bar sk-bar--w60"></div>
      <div class="sk-bar sk-bar--w30"></div>
      <div class="sk-bar sk-bar--w100"></div>
      <div class="sk-bar sk-bar--w95"></div>
      <div class="sk-bar sk-bar--w90"></div>
      <div class="sk-bar sk-bar--w75"></div>
    </template>

    <template v-else>
      <div class="sk-bar sk-bar--w50"></div>
      <div class="sk-bar sk-bar--w85"></div>
      <div class="sk-bar sk-bar--w70"></div>
    </template>
  </div>

  <section
    v-else-if="error || empty"
    class="state"
    :class="{ 'state--error': error, 'state--compact': compact }"
    :role="error ? 'alert' : 'status'"
    :aria-live="error ? undefined : 'polite'"
  >
    <p class="state__text">{{ error || emptyMessage }}</p>
    <div v-if="error" class="state__actions">
      <button type="button" class="btn" @click="$emit('retry')">{{ retryLabel }}</button>
    </div>
  </section>
</template>
