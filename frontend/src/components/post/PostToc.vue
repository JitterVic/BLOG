<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  items: { type: Array, required: true },
  activeId: { type: String, default: "" },
});

defineEmits(["navigate"]);

const navigationRef = ref(null);
let alignmentFrame = 0;
let resizeAlignmentTimer = 0;

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
  [() => props.activeId, () => props.items.length],
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
  <aside class="article-toc rv" data-reveal-delay="100">
    <div class="article-toc__head">
      <span>On this page</span>
      <strong>{{ String(items.length).padStart(2, "0") }}</strong>
    </div>
    <nav ref="navigationRef" aria-label="文章目录">
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
  </aside>
</template>
