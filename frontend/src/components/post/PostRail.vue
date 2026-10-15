<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { shortDate } from "../../composables/useFormat";
import { usePanelPin } from "../../composables/usePanelPin";
import { usePersistedCollapse } from "../../composables/usePersistedCollapse";
import { groupByYear } from "../../lib/postGroups";

/**
 * 文章页左侧清单：当前栏目的编年索引。
 *
 * 它住在阅读版式左边那条本来空置的 1fr 轨道里，并且贴左边缘对齐 —— 与右侧目录
 * 贴右边缘对称。这样折叠与否只改变自己的宽度，正文轨道的中心与宽度都不动，
 * 也就不会出现「折叠侧栏时文字在读者眼皮底下重排」。
 *
 * 高度上它与那条网格行解耦：外层 aside 高 0、不参与行高计算，展开态与书脊都由
 * 内部绝对定位撑开（见 post.css）。副作用是面板在到达吸附位置之前从行的顶部开始排，
 * 因此还得把「它自己顶部到视口底部」的剩余空间同步给 CSS，否则底部（含「完整目录」）
 * 会被屏幕裁掉，看起来像清单比左栏还长。越过吸附线后改由 .is-pinned 换成 fixed，
 * 滚动过程中不再写任何坐标（理由见 usePanelPin.js）。
 *
 * 行只给日期 + 标题：约 300px 宽放不下摘要，摘要留给 /posts 的索引。
 */
const props = defineProps({
  posts: { type: Array, required: true },
  total: { type: Number, default: 0 },
  hasMore: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  mode: { type: String, default: "category" },
  category: { type: String, default: "" },
  currentSlug: { type: String, default: "" },
});

defineEmits(["more"]);

// 展开态是默认：折起来虽然干净，但先折起来等于让人永远发现不了这一栏。
const { collapsed, collapse, expand } = usePersistedCollapse("zhizhi-article-rail-collapsed");

const navigationRef = ref(null);
const hostRef = ref(null);
let alignmentFrame = 0;
let resizeAlignmentTimer = 0;
const { pinned, parked } = usePanelPin(hostRef);

const groups = computed(() => groupByYear(props.posts));
const scopeLabel = computed(() => (props.mode === "latest" ? "最新" : props.category || "全部"));
const currentIndex = computed(() => props.posts.findIndex((post) => post.slug === props.currentSlug));
const allHref = computed(() => (
  props.mode === "category" && props.category
    ? `/posts?cat=${encodeURIComponent(props.category)}`
    : "/posts"
));

function pad(value) {
  return String(value).padStart(2, "0");
}

/**
 * 把当前篇滚进清单自己的可视区。
 *
 * 不用平滑滚动：清单在换篇时是整体重建的，一次动画滚动会在正文刚切换的同时
 * 让栏内文字横冲过去。只在真的越界时才动，避免每次挂载都把列表微调一下。
 */
function alignActiveRow() {
  alignmentFrame = 0;
  const navigation = navigationRef.value;
  const active = navigation?.querySelector(".is-current");
  if (!navigation || !active) return;

  const navigationRect = navigation.getBoundingClientRect();
  const activeRect = active.getBoundingClientRect();
  const edgeMargin = 12;

  if (activeRect.top < navigationRect.top + edgeMargin) {
    navigation.scrollTop += activeRect.top - navigationRect.top - edgeMargin;
  } else if (activeRect.bottom > navigationRect.bottom - edgeMargin) {
    navigation.scrollTop += activeRect.bottom - navigationRect.bottom + edgeMargin;
  }
}

async function scheduleAlignment() {
  if (collapsed.value) return;
  await nextTick();
  if (alignmentFrame) window.cancelAnimationFrame(alignmentFrame);
  alignmentFrame = window.requestAnimationFrame(alignActiveRow);
}

/**
 * 视口变矮后清单可视区也变矮，当前篇可能落到可视区之外——挂载时对齐过一次
 * 并不够，所以随 resize 再对齐（与右侧目录同一套做法）。
 */
async function handleResize() {
  await scheduleAlignment();
  window.clearTimeout(resizeAlignmentTimer);
  resizeAlignmentTimer = window.setTimeout(() => {
    resizeAlignmentTimer = 0;
    scheduleAlignment();
  }, 320);
}

watch(
  [() => props.posts.length, () => props.currentSlug, collapsed],
  scheduleAlignment,
  { flush: "post" },
);

onMounted(() => {
  window.addEventListener("resize", handleResize, { passive: true });
  scheduleAlignment();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  window.clearTimeout(resizeAlignmentTimer);
  if (alignmentFrame) window.cancelAnimationFrame(alignmentFrame);
});
</script>

<template>
  <aside
    ref="hostRef"
    class="article-rail"
    :class="{ 'is-collapsed': collapsed, 'is-parked': parked, 'is-pinned': pinned }"
    aria-label="文章清单"
  >
    <!-- 折叠态：贴左边缘的竖排书脊，点一下展开 -->
    <button
      v-if="collapsed"
      class="article-rail__spine"
      type="button"
      aria-expanded="false"
      title="展开文章清单"
      @click="expand"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
      <span class="article-rail__spine-label">文章清单</span>
      <strong>{{ pad(total) }}</strong>
    </button>

    <div v-else class="article-rail__body">
      <div class="article-rail__head">
        <span>{{ scopeLabel }}</span>
        <strong v-if="currentIndex >= 0">{{ currentIndex + 1 }}<i>/{{ total }}</i></strong>
        <strong v-else>{{ pad(total) }}</strong>
        <button
          class="article-rail__toggle"
          type="button"
          aria-expanded="true"
          title="收起文章清单"
          @click="collapse"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
        </button>
      </div>

      <nav ref="navigationRef" aria-label="文章清单导航">
        <template v-for="([year, items]) in groups" :key="year">
          <p class="article-rail__year">{{ year }}</p>
          <RouterLink
            v-for="post in items"
            :key="post.slug"
            :to="`/posts/${post.slug}`"
            class="article-rail__row"
            :class="{ 'is-current': post.slug === currentSlug }"
          >
            <span class="article-rail__date">{{ shortDate(post.published_at) }}</span>
            <em>{{ post.title }}</em>
          </RouterLink>
        </template>

        <button
          v-if="hasMore"
          class="article-rail__more"
          type="button"
          :disabled="loadingMore"
          @click="$emit('more')"
        >
          {{ loadingMore ? "加载中……" : "加载更多" }}
        </button>
      </nav>

      <RouterLink class="article-rail__all" :to="allHref">
        <span>完整目录</span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" /></svg>
      </RouterLink>
    </div>
  </aside>
</template>
