<script setup>
defineProps({
  loading: Boolean,
  error: { type: String, default: "" },
  empty: Boolean,
  loadingMessage: { type: String, default: "正在加载……" },
  emptyMessage: { type: String, default: "暂时没有内容。" },
  emptyTitle: { type: String, default: "暂无内容" },
  retryLabel: { type: String, default: "重试" },
});

defineEmits(["retry"]);
</script>

<template>
  <section
    v-if="loading || error || empty"
    class="async-state print-feedback"
    :class="{ 'async-state--error': error, 'async-state--empty': empty && !error }"
    :aria-busy="loading || undefined"
    :role="error ? 'alert' : 'status'"
    aria-live="polite"
  >
    <span class="async-state__eyebrow">{{ loading ? "Loading" : error ? "Error" : "Archive" }}</span>
    <strong>{{ loading ? loadingMessage : error ? "内容暂时无法打开" : emptyTitle }}</strong>
    <p>{{ error || emptyMessage }}</p>
    <button v-if="error" type="button" class="cover-button" @click="$emit('retry')">
      {{ retryLabel }}
    </button>
  </section>
</template>
