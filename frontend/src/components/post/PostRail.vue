<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { shortDate } from "../../composables/useFormat";
import { usePersistedCollapse } from "../../composables/usePersistedCollapse";
import { useRailHeight } from "../../composables/useRailHeight";
import { groupByYear } from "../../lib/postGroups";

/**
 * 文章页左侧清单：当前栏目的编年索引。
 *
 * 它住在阅读版式左边那条本来空置的 1fr 轨道里，并且贴左边缘对齐 —— 与右侧目录
 * 贴右边缘对称。这样折叠与否只改变自己的宽度，正文轨道的中心与宽度都不动，
 * 也就不会出现「折叠侧栏时文字在读者眼皮底下重排」。
 *
 * 行只给日期 + 标题：约 270px 宽放不下摘要，摘要留给 /posts 的索引。
 */
const props = defineProps({
  posts: { type: Array, required: true },
  total: { type: Number, default: 0 },
  hasMore: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  mode: { type: String, default: "category" },
  category: { type: String, default: "" },
  currentSlug: { type: String, default: "" },
  currentTitle: { type: String, default: "" },
  bodyRef: { type: Object, default: null },
  enabled: { type: Boolean, default: true },
});

defineEmits(["more"]);

// 展开态是默认：折起来虽然干净，但先折起来等于让人永远发现不了这一栏。
const { collapsed, collapse, expand } = usePersistedCollapse("zhizhi-article-rail-collapsed");
const { railMaxHeight } = useRailHeight(props.bodyRef, computed(() => props.enabled));

const navigationRef = ref(null);
let alignmentFrame = 0;

const groups = computed(() => groupByYear(props.posts));
const scopeLabel = computed(() => (props.mode === "latest" ? "最新" : props.category || "全部"));
const currentIndex = computed(() => props.posts.findIndex((post) => post.slug === props.currentSlug));
const currentMissing = computed(() => Boolean(props.currentSlug) && currentIndex.value < 0);
const allHref = computed(() => (
  props.mode === "category" && props.category
    ? `/posts?category=${encodeURIComponent(props.category)}`
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

watch(
  [() => props.posts.length, () => props.currentSlug, collapsed],
  scheduleAlignment,
  { flush: "post" },
);

onMounted(scheduleAlignment);

onBeforeUnmount(() => {
  if (alignmentFrame) window.cancelAnimationFrame(alignmentFrame);
});
</script>

<template>
  <aside
    class="article-rail rv"
    :class="{ 'is-collapsed': collapsed }"
    :style="railMaxHeight ? { maxHeight: `${railMaxHeight}px` } : undefined"
    data-reveal-delay="100"
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
          收起
        </button>
      </div>

      <nav ref="navigationRef" aria-label="文章清单导航">
        <div v-if="currentMissing" class="article-rail__current">
          <span>当前</span>
          <em>{{ currentTitle }}</em>
        </div>

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

      <RouterLink class="article-rail__all" :to="allHref">完整目录 →</RouterLink>
    </div>
  </aside>
</template>
