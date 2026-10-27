<script setup>
// 品牌封面（DESIGN.md §5.1）：首页顶部以描红笔序手写「知至而后意诚」——《大学》句，
// 与页脚座右铭「物格而后知至」首尾呼应（封面手写、页脚铅印）。
// 每次进入首页组件重挂载即重播一遍；每字描完后落墨（填充淡入）。
// 笔画数据自托管于 lib/brandStrokes.js（构建期抽取，运行时零网络请求）。
// 签名动效豁免（§7）：不随 prefers-reduced-motion 静默——纯描画与淡入、
// 无位移无布局抖动，任何环境都照常书写；印刷仍呈现落墨完成态（print.css）。

import { BRAND_CHARS, BRAND_TEXT } from "../../lib/brandStrokes";

const STROKE_MS = 70; // 单笔描完时长
const CHAR_GAP_MS = 130; // 字与字之间的换笔停顿
const INK_MS = 420; // 单字落墨淡入时长
const INK_DELAY_MS = 60; // 本字描完到落墨的间隔

// 预排时间轴：每笔的全局起始时刻 + 每字的落墨时刻（书写全程约 3.8s）
let cursor = 0;
const timeline = BRAND_CHARS.map((entry) => {
  const strokeDelays = entry.strokes.map(() => {
    const delay = cursor;
    cursor += STROKE_MS;
    return delay;
  });
  const inkDelay = cursor + INK_DELAY_MS;
  cursor += CHAR_GAP_MS;
  return { strokeDelays, inkDelay };
});

// 落款在末字落墨收笔后再现（留 80ms 换气）
const lastInk = timeline[timeline.length - 1].inkDelay;
const colophonDelay = lastInk + INK_MS + 80;

function strokeStyle(delay) {
  return { "--stroke-delay": `${delay}ms` };
}

function inkStyle(delay) {
  return { "--ink-delay": `${delay}ms` };
}
</script>

<template>
  <section
    class="brand-cover"
    role="img"
    :aria-label="`至知品牌题字：${BRAND_TEXT}，语出《礼记 · 大学》`"
  >
    <svg class="brand-cover__strokes" viewBox="0 0 6144 1024" aria-hidden="true">
      <g v-for="(entry, ci) in BRAND_CHARS" :key="entry.char" :transform="`translate(${ci * 1024} 0)`">
        <!-- 描红：沿笔顺逐笔勾勒笔画轮廓 -->
        <g transform="scale(1, -1) translate(0, -900)">
          <path
            v-for="(d, si) in entry.strokes"
            :key="`s${si}`"
            :d="d"
            pathLength="1"
            class="brand-stroke"
            :style="strokeStyle(timeline[ci].strokeDelays[si])"
          />
        </g>
        <!-- 落墨：本字描完后整字填充淡入 -->
        <g
          transform="scale(1, -1) translate(0, -900)"
          class="brand-fill"
          :style="inkStyle(timeline[ci].inkDelay)"
        >
          <path v-for="(d, si) in entry.strokes" :key="`f${si}`" :d="d" />
        </g>
      </g>
    </svg>
    <p class="brand-cover__colophon" :style="{ '--colophon-delay': `${colophonDelay}ms` }">——《礼记 · 大学》</p>
  </section>
</template>
