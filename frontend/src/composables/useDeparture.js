/**
 * 站内跳转确认感（模块级单例，与 useMagnetic 同模式）：
 * 按下文章卡片时先把卡片「按进纸面」（.is-departing），随后路由翻页动效接手，
 * 形成「这一张被抽走了」的叙事。
 *
 * 实现要点：
 * - 只认卡片类元素（头条卡 / 次要卡 / 热点行 / 目录行 / 封面要目），
 *   普通链接与按钮的按下反馈由 CursorEffects 的 .is-pressing 负责；
 * - 位移写独立的 translate / scale 属性，不碰元素自己的 transform
 *   （头条卡的 3D 倾斜、reveal 入场都走 transform，二者天然叠加）；
 * - reduced-motion 下不挂监听，一切保持原样；
 * - 类在 700ms 后摘除（略长于路由离场过渡），导航被打断也不残留。
 */
const DEPARTURE_SELECTOR = [
  ".print-feature-image",
  ".home-secondary-card",
  ".home-hot-row",
  ".archive__li",
  ".cover-toc__list a",
].join(", ");

const DEPARTURE_MS = 700;

let initialized = false;
const timers = new WeakMap();

function handlePointerDown(event) {
  if (event.button !== 0) return;
  const card = event.target?.closest?.(DEPARTURE_SELECTOR);
  if (!card || timers.has(card)) return;
  card.classList.add("is-departing");
  timers.set(card, window.setTimeout(() => {
    card.classList.remove("is-departing");
    timers.delete(card);
  }, DEPARTURE_MS));
}

/**
 * 启动跳转确认监听。只需调用一次（App.vue onMounted）；
 * 之后路由切换产生的卡片由下一次按下时实时匹配，无需重扫。
 */
export function initDeparture() {
  if (initialized || typeof window === "undefined") return;
  initialized = true;
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches) return;
  document.addEventListener("pointerdown", handlePointerDown, { passive: true });
}
