<script setup>
// 读迹 ReadTrace（DESIGN.md §6.3）——站点的签名：读完一篇描一画，五篇成一个「正」。
//
// 每组 viewBox 20×20，描边 2px 圆头，pathLength=1；写满的组全为墨色，
// 仅当前未写满的组显示底稿（--line）。最多 12 组（60 篇），更多只显示数字。
// 落笔动效：新的一画 stroke-dashoffset 1→0（360ms），仅当读迹所在栏可见时播放。

import { computed, onBeforeUnmount, ref, watch } from "vue";

import { useReadLog } from "../composables/useReadLog";

const MAX_GROUPS = 12;

// 画序（§6.3）：上横、中竖、中短横、左短竖、下横
const STROKES = [
  "M3 3H17",
  "M10 3V17",
  "M10 9.5H15.5",
  "M5.5 9V17",
  "M3 17H17",
];

const { readable, readCount, totalCount, ensureCatalog } = useReadLog();
ensureCatalog();

const rootRef = ref(null);
const animatingStroke = ref(null); // { group, stroke }：正在落笔的那一画
let animTimer = 0;

const groups = computed(() => {
  const count = readCount.value;
  const full = Math.floor(count / 5);
  const rest = count % 5;
  const total = full + (rest > 0 ? 1 : 0);
  const result = [];
  for (let i = 0; i < Math.min(total, MAX_GROUPS); i += 1) {
    result.push({
      index: i,
      // 组内已描画数：写满的组 5 画，当前组 rest 画
      drawn: i < full ? 5 : rest,
      isCurrent: i === full && rest > 0,
    });
  }
  return result;
});

const showStrokes = computed(() => readCount.value > 0 && readCount.value <= MAX_GROUPS * 5);

/** 读迹栏此刻真的可见（左栏常驻；菜单里的副本仅在 dialog 打开时可见）。 */
function isTraceVisible() {
  const el = rootRef.value;
  if (!el || !el.isConnected) return false;
  const dialog = el.closest("dialog");
  if (dialog && !dialog.open) return false;
  return el.getBoundingClientRect().height > 0;
}

watch(readCount, (count, prev) => {
  if (!count || count <= prev) return;
  if (!isTraceVisible()) return;
  animatingStroke.value = { group: Math.floor((count - 1) / 5), stroke: (count - 1) % 5 };
  window.clearTimeout(animTimer);
  animTimer = window.setTimeout(() => {
    animatingStroke.value = null;
  }, 420);
});

onBeforeUnmount(() => window.clearTimeout(animTimer));
</script>

<template>
  <div v-if="readable" ref="rootRef" class="read-trace">
    <div
      v-if="showStrokes"
      class="read-trace__strokes"
      role="img"
      :aria-label="`已读 ${readCount} 篇，共 ${totalCount} 篇`"
    >
      <svg
        v-for="group in groups"
        :key="group.index"
        class="read-trace__glyph"
        viewBox="0 0 20 20"
        aria-hidden="true"
      >
        <path
          v-for="(stroke, si) in STROKES"
          :key="si"
          :d="stroke"
          pathLength="1"
          class="read-trace__stroke"
          :class="{
            'is-drawn': si < group.drawn,
            'is-guide': group.isCurrent && si >= group.drawn,
            'is-animating':
              animatingStroke
              && animatingStroke.group === group.index
              && animatingStroke.stroke === si,
          }"
        />
      </svg>
    </div>
    <p v-if="totalCount" class="read-trace__meta">已读 {{ readCount }} / 共 {{ totalCount }} 篇</p>
  </div>
</template>
