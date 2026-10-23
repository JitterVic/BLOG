import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useRoute } from "vue-router";

/**
 * 首页整屏翻页（幻灯片式，单例 Composable，与 useSite 同模式）：
 * - 文档不滚动：home-paging 模式下 html/body overflow: hidden（见 pages.css）；
 * - 三版装进 .flip-track，滚轮/键盘/触摸只改变 currentPage，
 *   轨道以 transform: translateY 整体切页——第一页直接滑走、第二页顶上来；
 * - 动画锁保证一次手势只翻一页；
 * - 所有视口统一使用三页整屏翻页。
 */
const PAGE_COUNT = 3; // 封面 001 / 最近更新 002 / 热点文章 003
const FLIP_LOCK_MS = 850;
const MIN_WHEEL_DELTA = 4;
const MIN_TOUCH_DISTANCE = 48;

const currentPage = ref(0);
const isFlipActive = ref(false);

let listening = false;
let active = false;
let lockUntil = 0;
let touchStartY = null;
function syncFlipActive() {
  isFlipActive.value = active;
  if (!isFlipActive.value) currentPage.value = 0;
}

function goToPage(index) {
  const target = Math.min(Math.max(index, 0), PAGE_COUNT - 1);
  if (target === currentPage.value) return;
  lockUntil = performance.now() + FLIP_LOCK_MS;
  currentPage.value = target;
}

/** 供封面锚点按钮使用：翻页模式下接管点击，否则放行原生锚点跳转。 */
function navigateToPage(index, event) {
  if (!isFlipActive.value) return;
  event?.preventDefault();
  goToPage(index);
}

function flip(direction) {
  goToPage(currentPage.value + direction);
}

function handleWheel(event) {
  if (!active) return;
  event.preventDefault();
  if (performance.now() < lockUntil) return;
  if (Math.abs(event.deltaY) < MIN_WHEEL_DELTA) return;
  flip(event.deltaY > 0 ? 1 : -1);
}

/** 焦点是否落在可交互控件上：这些元素自己消费 Space/方向键，翻页不能抢。 */
function isInteractiveTarget(target) {
  if (!target || typeof target.closest !== "function") return false;
  return Boolean(
    target.closest(
      "a, button, input, textarea, select, summary, label, [contenteditable=''], [contenteditable='true'], [role='button'], [role='link'], [role='menuitem'], [role='menuitemradio'], [role='tab'], [role='switch']",
    ),
  );
}

function handleKeydown(event) {
  if (!active) return;
  const tag = event.target?.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || event.target?.isContentEditable) return;
  // 此前只排除输入框：焦点停在「开始阅读」等按钮上时按 Space，
  // 这里 preventDefault 掉的是按钮的激活键，键盘用户被锁死在首页翻页里。
  if (isInteractiveTarget(event.target)) return;

  if (["ArrowDown", "PageDown", " "].includes(event.key)) {
    event.preventDefault();
    flip(1);
  } else if (["ArrowUp", "PageUp"].includes(event.key)) {
    event.preventDefault();
    flip(-1);
  } else if (event.key === "Home") {
    event.preventDefault();
    goToPage(0);
  } else if (event.key === "End") {
    event.preventDefault();
    goToPage(PAGE_COUNT - 1);
  }
}

function handleTouchStart(event) {
  if (!active) return;
  touchStartY = event.touches[0]?.clientY ?? null;
}

function handleTouchEnd(event) {
  if (touchStartY === null || !active) return;
  const delta = touchStartY - (event.changedTouches[0]?.clientY ?? touchStartY);
  touchStartY = null;
  if (Math.abs(delta) < MIN_TOUCH_DISTANCE) return;
  if (performance.now() < lockUntil) return;
  flip(delta > 0 ? 1 : -1);
}

function activate() {
  if (listening) return;
  listening = true;
  active = true;
  currentPage.value = 0;
  window.addEventListener("wheel", handleWheel, { passive: false });
  window.addEventListener("keydown", handleKeydown);
  window.addEventListener("touchstart", handleTouchStart, { passive: true });
  window.addEventListener("touchend", handleTouchEnd, { passive: true });
  window.addEventListener("resize", syncFlipActive, { passive: true });
  syncFlipActive();
}

function deactivate() {
  if (!listening) return;
  listening = false;
  active = false;
  currentPage.value = 0;
  isFlipActive.value = false;
  touchStartY = null;
  window.removeEventListener("wheel", handleWheel);
  window.removeEventListener("keydown", handleKeydown);
  window.removeEventListener("touchstart", handleTouchStart);
  window.removeEventListener("touchend", handleTouchEnd);
  window.removeEventListener("resize", syncFlipActive);
}

export function usePageFlip() {
  const route = useRoute();

  watch(
    () => route.name,
    (name) => {
      if (name === "home") activate();
      else deactivate();
    },
    { immediate: true },
  );

  onBeforeUnmount(deactivate);

  /** 轨道位移样式：仅在翻页模式下应用，回退模式不产生任何变换 */
  const trackStyle = computed(() => (
    isFlipActive.value
      ? { transform: `translate3d(0, -${currentPage.value * 100}svh, 0)` }
      : {}
  ));

  return {
    currentPage,
    isFlipActive,
    trackStyle,
    goToPage,
    navigateToPage,
  };
}
