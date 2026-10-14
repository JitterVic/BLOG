import { nextTick, onMounted, onUnmounted, watch } from "vue";
import { useRoute } from "vue-router";

const DEFAULT_SELECTOR = ".rv:not(.vis)";
const DEFAULT_ROOT_MARGIN = "0px 0px -6% 0px";
const DEFAULT_THRESHOLD = 0.08;
// 兜底放行的宽限：只用于「观察器彻底没工作」这种异常，不能拿它当常规揭示手段。
const SAFETY_REVEAL_MS = 4000;
// 阶梯延迟上限。未显式声明 `data-reveal-delay` 的元素按「揭示序号 × staggerMs」计算，
// 而序号在整页范围内累加——长文章里一旦有上百个这类元素，最后几个的延迟会涨到数秒，
// 表现为「内容迟迟不出现」（实测长文章页仍有元素在 5s 后才淡入）。这里给阶梯封顶，
// 只保留「同批元素依次登场」的观感，不让延迟无界增长。
const MAX_STAGGER_STEPS = 8;
// 手动关闭动效的存储键（值为 "off" 时停用入场动效并立即显示全部内容）。
export const MOTION_STORAGE_KEY = "zhizhi-motion";

function prefersReducedMotion() {
  if (typeof window === "undefined" || !window.matchMedia) {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function revealAll(root, selector) {
  if (!root) return;
  const query = selector.includes(":not(.vis)")
    ? selector
    : `${selector}:not(.vis)`;
  root.querySelectorAll(query.replace(":not(.vis)", "") || ".rv").forEach((el) => {
    el.classList.add("vis");
  });
  // Always force-visible any leftover .rv
  root.querySelectorAll(".rv:not(.vis)").forEach((el) => {
    el.classList.add("vis");
  });
}

/**
 * 用户是否显式要求关闭动效。
 * 判定两个来源：
 * 1. 系统/浏览器的 `prefers-reduced-motion`（Windows「显示动画」关闭时 Chrome/Edge 会上报 reduce）；
 * 2. `localStorage.zhizhi-motion`，用于在本机偏好与系统设置不一致时手动覆盖：
 *    "off" 强制关闭，"on" 强制开启（可覆盖系统 reduce），未设置则跟随系统。
 */
export function motionDisabled() {
  try {
  const stored = window.localStorage.getItem(MOTION_STORAGE_KEY);
  if (stored === "off") return true;
  if (stored === "on") return false;
  } catch {
  // 隐私模式下 localStorage 不可用，跟随系统偏好。
  }
  return prefersReducedMotion();
}

/** 系统/浏览器层面的动效偏好（不含手动覆盖），供开关显示初始状态。 */
export function systemMotionDisabled() {
  return prefersReducedMotion();
}

/**
 * 把「关闭动效」状态同步到根元素。
 *
 * 必须成对切换两个类，二者缺一不可：
 * - `motion-off`：关闭时启用降级样式；
 * - `motion-on`：**开启时**也要打标，因为 CSS 里用 `html:not(.motion-on)` 作为
 *   reduced-motion 兜底的选择器——若只加 `motion-off` 而从不加 `motion-on`，
 *   那个 `:not()` 会恒为真，用户手动开启动效在系统 reduce 下完全失效。
 */
export function applyMotionClass(disabled) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("motion-off", disabled);
  document.documentElement.classList.toggle("motion-on", !disabled);
}

/**
 * Progressive reveal for elements with the `.rv` class.
 * Adds `.vis` when they enter the viewport, with staggered delays for siblings.
 */
export function useReveal(options = {}) {
  const {
    root = null,
    selector = DEFAULT_SELECTOR,
    rootMargin = DEFAULT_ROOT_MARGIN,
    threshold = DEFAULT_THRESHOLD,
    staggerMs = 64,
    reobserveOnRoute = true,
  } = options;

  let observer = null;
  let observed = new WeakSet();
  let staggerIndex = 0;
  let safetyTimer = 0;
  // 观察器是否真的产生过交集：决定兜底放行要不要执行（见 observeTargets）。
  let sawIntersection = false;

  function getRoot() {
    if (root?.value) return root.value;
    if (typeof document !== "undefined") return document;
    return null;
  }

  function clearSafety() {
    if (safetyTimer) {
      window.clearTimeout(safetyTimer);
      safetyTimer = 0;
    }
  }

  function disconnect() {
    clearSafety();
    if (observer) {
      observer.disconnect();
      observer = null;
    }
    observed = new WeakSet();
    staggerIndex = 0;
    sawIntersection = false;
  }

  function markVisible(el) {
    if (!el || el.classList.contains("vis")) return;
    const delay = Number(el.dataset.revealDelay ?? Math.min(staggerIndex, MAX_STAGGER_STEPS) * staggerMs);
    el.style.setProperty("--reveal-delay", `${delay}ms`);
    staggerIndex += 1;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.classList.add("vis");
      });
    });
  }

  /** 摘掉根元素上的 motion-off 标记（手动开启动效后需要让 CSS 回到动画态）。 */
  function syncMotionClass() {
    applyMotionClass(motionDisabled());
  }

  // 首次观察前先对齐一次根元素标记：main.js 只在挂载前读过一次 localStorage，
  // 之后若用户改了设置（或系统偏好变化），这里要跟上。

  /** 供外部（如站头开关）在切换动效偏好后立即重算揭示状态。 */
  function refreshMotion() {
    syncMotionClass();
    disconnect();
    refresh();
  }

  /**
   * 让 `root` 内的 `.rv` 重新入场（用于首页整屏翻页：翻页时正文不滚动，
   * IntersectionObserver 不会重新触发，被切走的版面也因此不会重播）。
   *
   * 分两帧做完：先摘掉 `.vis` 回到基准态，下一帧再标回——否则同一帧内增删
   * 类名不会触发过渡。逐元素延迟沿用 `data-reveal-delay`，与观察器路径一致。
   */
  function replayReveal(root) {
    if (!root || typeof window === "undefined") return;
    const targets = Array.from(root.querySelectorAll(".rv"));
    if (!targets.length) return;
    if (motionDisabled()) {
      targets.forEach((el) => el.classList.add("vis"));
      return;
    }

    // 先回到基准态，并**强制一次样式计算**（读 offsetWidth）——只靠 rAF 不足以保证
    // 浏览器在「摘掉 .vis」和「加回 .vis」之间真的产出一帧中间样式，
    // 实测那样不会触发过渡（vis 在 2 帧内 4→0→4，但 opacity 始终是 4）。
    targets.forEach((el) => el.classList.remove("vis"));
    void root.offsetWidth;

    targets.forEach((el, index) => {
      const delay = Number(el.dataset.revealDelay ?? Math.min(index, MAX_STAGGER_STEPS) * 64);
      el.style.setProperty("--reveal-delay", `${delay}ms`);
      el.classList.add("vis");
    });
  }

  /** 与 replayReveal 相反：把版面复位成「未揭示」，下次进入才会重新播放。 */
  function resetReveal(root) {
    if (!root) return;
    root.querySelectorAll(".rv").forEach((el) => el.classList.remove("vis"));
  }

  function observeTargets() {
    const host = getRoot();
    if (!host || typeof window === "undefined") return;

    if (motionDisabled()) {
      revealAll(host, selector);
      return;
    }

    if (!("IntersectionObserver" in window)) {
      revealAll(host, selector);
      return;
    }

    if (!observer) {
      observer = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (!entry.isIntersecting) continue;
            sawIntersection = true;
            const el = entry.target;
            markVisible(el);
            observer.unobserve(el);
          }
        },
        { root: null, rootMargin, threshold },
      );
    }

    const targets = host.querySelectorAll(".rv:not(.vis)");
    targets.forEach((el) => {
      if (observed.has(el)) return;
      observed.add(el);
      observer.observe(el);
    });

    // Safety net: never leave content permanently invisible.
    // 注意 `markVisible` 会把元素标成 `.vis`，而观察器只处理 `.rv:not(.vis)`，
    // 所以这个兜底一旦提前跑，就等于把还没滚到的内容全部预先揭示——之后滚动
    // 到它们时就不会再播放入场动效（实测 1600ms 兜底会让首页第 2/3 版共 7 个
    // 元素在翻页前就已 `vis`，翻过去时动画全无）。
    // 因此这里只判定「观察器是否真的在工作」：正常浏览时 observer 必然已产生
    // 过交集记录，此时不再兜底；只有当观察器完全没动作时才放行。
    clearSafety();
    safetyTimer = window.setTimeout(() => {
      if (sawIntersection) return;
      const leftover = host.querySelectorAll(".rv:not(.vis)");
      leftover.forEach((el) => markVisible(el));
    }, SAFETY_REVEAL_MS);
  }

  async function refresh() {
    await nextTick();
    requestAnimationFrame(() => {
      observeTargets();
    });
  }

  onMounted(() => {
    syncMotionClass();
    refresh();
  });

  onUnmounted(() => {
    disconnect();
  });

  if (reobserveOnRoute) {
    try {
      const route = useRoute();
      watch(
        () => route.fullPath,
        () => {
          disconnect();
          refresh();
        },
      );
    } catch {
      // useRoute is only available inside a component setup context.
    }
  }

  return {
    refresh,
    refreshMotion,
    replayReveal,
    resetReveal,
    disconnect,
  };
}
