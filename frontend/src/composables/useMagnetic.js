/**
 * 磁吸按钮（模块级单例，与 useSite 同模式）：
 * 光标进入可点元素周围的「引力圈」时，元素被轻轻拉向指针，离开后弹回原位。
 *
 * 实现要点：
 * - 位移写 CSS 独立的 `translate` 属性，与样式表里的 transform
 *   （hover 上浮 / :active 下沉）互不覆盖、自然叠加；
 * - 只在 (pointer: fine) 且未要求减少动效时启用，触摸设备整体跳过；
 * - 全部计算合并进一个 rAF 循环，空闲（无吸附、无回弹）时自动停摆；
 * - 元素矩形缓存，scroll / resize / DOM 增删（MutationObserver 防抖）/
 *   首页翻轨 transitionend 时重取——翻页时元素随轨道位移，矩形必须在翻完后重取。
 */
const MAGNETIC_SELECTOR = [
  ".cover-button",
  ".print-nav__item",
  ".cat-filter-button",
  ".print-menu-button",
  ".print-scroll-cue",
].join(", ");

const PULL_RADIUS = 30; // 元素边缘外引力圈的厚度（px）
const MAX_PULL = 7; // 最大吸附位移（px）
const PULL_RATIO = 0.28; // 指针距中心位移的吸附系数
const EASE = 0.16; // 吸附 / 回弹共用的插值系数
const SETTLE_EPSILON = 0.08; // 小于该位移视为已回位
const RECT_THROTTLE_MS = 160;
const RESCAN_DEBOUNCE_MS = 220;

let initialized = false;
let enabled = false;
let candidates = [];
let rafId = 0;
let pointerX = 0;
let pointerY = 0;
let pointerActive = false;
let rectTimer = 0;
let rescanTimer = 0;
let mutationObserver = null;
let fineQuery = null;
let motionQuery = null;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function shouldEnable() {
  const fine = fineQuery?.matches
    ?? window.matchMedia?.("(pointer: fine)")?.matches
    ?? false;
  const reduced = motionQuery?.matches
    ?? window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
    ?? false;
  return fine && !reduced;
}

function scanCandidates() {
  candidates = Array.from(document.querySelectorAll(MAGNETIC_SELECTOR))
    .filter((el) => el.isConnected)
    .map((el) => ({ el, rect: el.getBoundingClientRect(), x: 0, y: 0 }));
}

function refreshRects() {
  for (const item of candidates) {
    if (!item.el.isConnected) continue;
    item.rect = item.el.getBoundingClientRect();
  }
}

function scheduleRescan() {
  window.clearTimeout(rescanTimer);
  rescanTimer = window.setTimeout(() => {
    rescanTimer = 0;
    scanCandidates();
  }, RESCAN_DEBOUNCE_MS);
}

function scheduleRectRefresh() {
  if (rectTimer) return;
  rectTimer = window.setTimeout(() => {
    rectTimer = 0;
    refreshRects();
  }, RECT_THROTTLE_MS);
}

function tick() {
  rafId = 0;
  let busy = false;

  for (const item of candidates) {
    const r = item.rect;
    let targetX = 0;
    let targetY = 0;

    if (
      pointerActive
      && pointerX >= r.left - PULL_RADIUS
      && pointerX <= r.right + PULL_RADIUS
      && pointerY >= r.top - PULL_RADIUS
      && pointerY <= r.bottom + PULL_RADIUS
    ) {
      const centerX = r.left + r.width / 2;
      const centerY = r.top + r.height / 2;
      targetX = clamp((pointerX - centerX) * PULL_RATIO, -MAX_PULL, MAX_PULL);
      targetY = clamp((pointerY - centerY) * PULL_RATIO, -MAX_PULL, MAX_PULL);
    }

    item.x += (targetX - item.x) * EASE;
    item.y += (targetY - item.y) * EASE;
    if (!targetX && !targetY) {
      if (Math.abs(item.x) < SETTLE_EPSILON) item.x = 0;
      if (Math.abs(item.y) < SETTLE_EPSILON) item.y = 0;
    }

    if (item.x || item.y) {
      busy = true;
      item.el.style.translate = `${item.x.toFixed(2)}px ${item.y.toFixed(2)}px`;
    } else if (item.el.style.translate) {
      item.el.style.translate = "";
    }

    if (targetX || targetY) busy = true;
  }

  if (busy) rafId = window.requestAnimationFrame(tick);
}

function scheduleTick() {
  if (!rafId) rafId = window.requestAnimationFrame(tick);
}

function handlePointerMove(event) {
  if (!enabled || event.pointerType === "touch") return;
  pointerX = event.clientX;
  pointerY = event.clientY;
  pointerActive = true;
  scheduleTick();
}

function handlePointerLeave() {
  pointerActive = false;
  scheduleTick();
}

function handleScrollOrResize() {
  scheduleRectRefresh();
}

function handleTransitionEnd(event) {
  // 首页翻轨完成：版面元素随轨道整体位移过，矩形缓存已失效。
  if (event.propertyName === "transform" && event.target?.classList?.contains("flip-track")) {
    refreshRects();
  }
}

function handlePreferenceChange() {
  const next = shouldEnable();
  if (next === enabled) return;
  enabled = next;
  if (!enabled) {
    // 关闭时把所有吸附位移归零，避免元素停在偏移状态
    for (const item of candidates) {
      item.x = 0;
      item.y = 0;
      item.el.style.translate = "";
    }
    candidates = [];
  } else {
    scanCandidates();
  }
}

/**
 * 启动磁吸监听。只需调用一次（App.vue onMounted）；
 * 之后的路由切换与内容增删由 MutationObserver 自行跟踪。
 */
export function initMagnetic() {
  if (initialized || typeof window === "undefined") return;
  initialized = true;

  fineQuery = window.matchMedia?.("(pointer: fine)") || null;
  motionQuery = window.matchMedia?.("(prefers-reduced-motion: reduce)") || null;
  fineQuery?.addEventListener?.("change", handlePreferenceChange);
  motionQuery?.addEventListener?.("change", handlePreferenceChange);
  enabled = shouldEnable();

  document.addEventListener("pointermove", handlePointerMove, { passive: true });
  document.addEventListener("pointerleave", handlePointerLeave, { passive: true });
  document.addEventListener("transitionend", handleTransitionEnd, { passive: true });
  window.addEventListener("scroll", handleScrollOrResize, { passive: true });
  window.addEventListener("resize", handleScrollOrResize, { passive: true });

  mutationObserver = new MutationObserver(scheduleRescan);
  mutationObserver.observe(document.body, { childList: true, subtree: true });

  if (enabled) scanCandidates();
}
