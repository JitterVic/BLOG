<script setup>
defineProps({
  src: { type: String, default: "" },
  alt: { type: String, default: "" },
});

defineEmits(["close", "backdrop"]);
</script>

<template>
  <dialog
    class="article-lightbox"
    aria-label="文章图片预览"
    @click="$emit('backdrop', $event)"
    @cancel.prevent="$emit('close')"
  >
    <button type="button" class="article-lightbox__close" aria-label="关闭图片预览" @click="$emit('close')">
      CLOSE ×
    </button>
    <figure>
      <img :src="src" :alt="alt" decoding="async">
      <figcaption v-if="alt">{{ alt }}</figcaption>
    </figure>
  </dialog>
</template>
