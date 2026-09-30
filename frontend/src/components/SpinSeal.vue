<script setup>
import { computed } from "vue";

/**
 * 旋转印章：环形文字围绕中心字缓慢旋转的报纸刊头装饰。
 * 仅 transform 旋转动画，reduced-motion 下静止（见 styles/feedback.css）。
 */
const props = defineProps({
  text: { type: String, default: "ZHIZHI JOURNAL · PERSONAL TECH PRESS · EST. 2026 · " },
  center: { type: String, default: "至" },
  size: { type: Number, default: 120 },
});

// 闭合圆环路径：以 50,50 为圆心，半径 40
const ringPath = "M 50,50 m -40,0 a 40,40 0 1,1 80,0 a 40,40 0 1,1 -80,0";
const styleVars = computed(() => ({ "--seal-size": `${props.size}px` }));
</script>

<template>
  <div class="spin-seal" :style="styleVars" aria-hidden="true">
    <svg class="spin-seal__ring" viewBox="0 0 100 100" focusable="false">
      <defs>
        <path :id="`seal-ring-${size}`" :d="ringPath" fill="none" />
      </defs>
      <text class="spin-seal__text">
        <textPath :href="`#seal-ring-${size}`" textLength="250" lengthAdjust="spacingAndGlyphs">
          {{ text }}
        </textPath>
      </text>
    </svg>
    <span class="spin-seal__center">{{ center }}</span>
  </div>
</template>
