<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { useMediaQuery } from "../../composables/useMediaQuery";
import { usePersistedCollapse } from "../../composables/usePersistedCollapse";

const props = defineProps({
  items: { type: Array, required: true },
  activeId: { type: String, default: "" },
});

defineEmits(["navigate"]);

const navigationRef = ref(null);
let alignmentFrame = 0;
let resizeAlignmentTimer = 0;

// 折叠只属于桌面竖排目录。窄屏那条横向胶囊目录条本来就只占一行，
// 没有可折的余地；若把偏好直接套上去，在桌面折过目录的人一缩小窗口
// 就会看到整条目录变成书脊。
const isDesktop = useMediaQuery("(min-width: 1281px)");
const { collapsed, collapse, expand } = usePersistedCollapse("zhizhi-article-toc-collapsed");
const isCollapsed = computed(() => isDesktop.value && collapsed.value);

// 书脊上留当前章节号：目录可以收起来，「我读到第几节」不该跟着消失。
const activeIndex = computed(() => props.items.findIndex((item) => item.id === props.activeId));

function pad(value) {
  return String(value).padStart(2, "0");
}

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false;
}

function alignActiveItem(behavior = prefersReducedMotion() ? "auto" : "smooth") {
  alignmentFrame = 0;
  const navigation = navigationRef.value;
  const activeItem = navigation?.querySelector('[aria-current="location"]');
  if (!navigation || !activeItem) return;

  const navigationRect = navigation.getBoundingClientRect();
  const activeRect = activeItem.getBoundingClientRect();
  const edgeMargin = 12;
  const scrollOptions = { behavior };

  if (window.matchMedia?.("(max-width: 1280px)").matches) {
    if (activeRect.left < navigationRect.left + edgeMargin) {
      navigation.scrollTo({
        ...scrollOptions,
        left: navigation.scrollLeft + activeRect.left - navigationRect.left - edgeMargin,
      });
    } else if (activeRect.right > navigationRect.right - edgeMargin) {
      navigation.scrollTo({
        ...scrollOptions,
        left: navigation.scrollLeft + activeRect.right - navigationRect.right + edgeMargin,
      });
    }
    return;
  }

  if (activeRect.top < navigationRect.top + edgeMargin) {
    navigation.scrollTo({
      ...scrollOptions,
      top: navigation.scrollTop + activeRect.top - navigationRect.top - edgeMargin,
    });
  } else if (activeRect.bottom > navigationRect.bottom - edgeMargin) {
    navigation.scrollTo({
      ...scrollOptions,
      top: navigation.scrollTop + activeRect.bottom - navigationRect.bottom + edgeMargin,
    });
  }
}

function queueAlignment(behavior, waitForLayout = false) {
  if (alignmentFrame) window.cancelAnimationFrame(alignmentFrame);

  const run = () => {
    alignmentFrame = window.requestAnimationFrame(() => {
      alignmentFrame = 0;
      alignActiveItem(behavior);
    });
  };

  if (waitForLayout) {
    alignmentFrame = window.requestAnimationFrame(run);
  } else {
    run();
  }
}

async function scheduleAlignment() {
  if (isCollapsed.value) return;
  await nextTick();
  queueAlignment(prefersReducedMotion() ? "auto" : "smooth", true);
}

async function handleResize() {
  await nextTick();
  queueAlignment("auto", true);
  window.clearTimeout(resizeAlignmentTimer);
  resizeAlignmentTimer = window.setTimeout(() => {
    resizeAlignmentTimer = 0;
    queueAlignment("auto", true);
  }, 320);
}

watch(
  [() => props.activeId, () => props.items.length, isCollapsed, isDesktop],
  scheduleAlignment,
  { flush: "post" },
);

onMounted(() => {
  window.addEventListener("resize", handleResize, { passive: true });
  scheduleAlignment();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  if (alignmentFrame) window.cancelAnimationFrame(alignmentFrame);
  window.clearTimeout(resizeAlignmentTimer);
});
</script>

<template>
  <aside
    class="article-toc rv"
    :class="{ 'is-collapsed': isCollapsed }"
    data-reveal-delay="100"
  >
    <!-- 折叠态：贴右边缘的竖排书脊，保留当前章节号 -->
    <button
      v-if="isCollapsed"
      class="article-toc__spine"
      type="button"
      aria-expanded="false"
      aria-controls="article-toc-nav"
      title="展开目录"
      @click="expand"
    >
      <span class="article-toc__spine-label">目录</span>
      <strong>{{ pad(activeIndex >= 0 ? activeIndex + 1 : items.length) }}</strong>
    </button>

    <template v-else>
      <div class="article-toc__head">
        <span>On this page</span>
        <strong>{{ String(items.length).padStart(2, "0") }}</strong>
        <button
          v-if="isDesktop"
          class="article-toc__toggle"
          type="button"
          aria-expanded="true"
          aria-controls="article-toc-nav"
          title="收起目录"
          @click="collapse"
        >
          收起
        </button>
      </div>
      <nav id="article-toc-nav" ref="navigationRef" aria-label="文章目录">
        <button
          v-for="(item, index) in items"
          :key="item.id"
          type="button"
          :class="{ active: activeId === item.id, 'is-subsection': item.level === 3 }"
          :aria-current="activeId === item.id ? 'location' : undefined"
          @click="$emit('navigate', item.id)"
        >
          <span>{{ String(index + 1).padStart(2, "0") }}</span>
          <em>{{ item.label }}</em>
        </button>
      </nav>
      <p>阅读时，目录会跟随当前章节。</p>
    </template>
  </aside>
</template>
