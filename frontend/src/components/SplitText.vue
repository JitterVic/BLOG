<script setup>
import { computed } from "vue";

/**
 * 逐字浮现文本：将文本拆分为单字，配合祖先的 `.vis`（useReveal）
 * 或 `.is-active`（InitialLoader）类触发排印式逐字上滑动画。
 * 动画样式定义在 styles/feedback.css，遵循 prefers-reduced-motion。
 *
 * 约定：必须存在带 `.vis` / `.is-active` 的祖先，否则单字停在 `opacity: 0`。
 * 两个调用点（首页封面标题、加载页标题）都已满足，新增用法时注意补上。
 */
const props = defineProps({
  text: { type: String, required: true },
  tag: { type: String, default: "span" },
  // 首个字的延迟（毫秒），用于与周边元素的显现节奏衔接
  baseDelay: { type: Number, default: 0 },
  // 相邻字之间的阶梯延迟（毫秒）
  step: { type: Number, default: 46 },
});

const chars = computed(() =>
  Array.from(props.text).map((char, index) => ({
    char: char === " " ? " " : char,
    delay: `${props.baseDelay + index * props.step}ms`,
  })),
);
</script>

<template>
  <component :is="tag" class="split-text" :aria-label="text">
    <span
      v-for="(item, index) in chars"
      :key="index"
      class="split-text__mask"
      aria-hidden="true"
    >
      <span class="split-text__char" :style="{ '--char-delay': item.delay }">{{ item.char }}</span>
    </span>
  </component>
</template>
