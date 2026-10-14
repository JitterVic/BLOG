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
 * 是否停用入场动效。
 *
 * 默认**不停用**：本站以视觉呈现为主，动效是版式的一部分，页面切换就应当播放，
 * 不能因为操作系统层面关了「显示动画」就整站变成静态（那样首页会失去开场的层次）。
 * 只保留一个手动开关（`localStorage.zhizhi-motion = "off"`）供需要时使用。
 */
export function motionDisabled() {
  if (typeof window === "undefined") return false;
  try {
  return window.localStorage.getItem(MOTION_STORAGE_KEY) === "off";
  } catch {
  // 隐私模式：视为默认开启。
  return false;
  }
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
  // 已揭示的动画名序号，用于「重播」时换名触发（见 replayCharAnimations）
  let animSeq = 0;
  // 供「重播」轮换的入场动画名。三组 keyframes 内容完全相同，只是名字不同——
  // 换名是唯一能可靠重启动画的手段（增删 class 会被浏览器在同一帧内合并掉）。
  const RISE_ANIMATIONS = ["split-char-rise", "split-char-rise-b", "split-char-rise-c"];
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

  /**
   * 换一个动画名，强制元素上的入场动画从头重播。
   *
   * 这是「重播」的关键：通过 class 增删来重启动画会受制于浏览器在帧末统一计算样式的机制
   * （同一任务内摘掉再加回 `.vis`，净状态不变则动画不重来），实测无效。
   * `animation-name` 从一个名字变成另一个名字则一定重启，配合 `both` 填充不受时序影响。
   */
  function replayCharAnimations(root) {
    const chars = root.querySelectorAll(".split-text__char");
    if (!chars.length) return;
    // 序号「每次重播只前进一格」——若按元素逐个前进，当元素个数是名字个数的整数倍时
    // （首页封面恰好 9 个单字 × 3 个名字）会绕回同名，动画不会重启（实测踩过）。
    animSeq = (animSeq + 1) % RISE_ANIMATIONS.length;
    const name = RISE_ANIMATIONS[animSeq];
    chars.forEach((char) => char.style.setProperty("--rise-name", name));
  }

  /** 手动关闭动效时给根元素打标记（`zhizhi-motion = "off"`，无 UI 入口）。 */
  function syncMotionClass() {
    if (typeof document === "undefined") return;
    document.documentElement.classList.toggle("motion-off", motionDisabled());
  }

  /**
   * 让 `root` 内的内容重新入场（用于首页整屏翻页与路由切换：这两种情况下正文
   * 并不滚动，IntersectionObserver 不会重新触发，被切走的版面也因此不会重播）。
   *
   * 两步缺一不可：
   * 1. 把 `.rv` 的 `.vis` 摘掉再标回，让容器级的入场动效重来；
   * 2. 给逐字浮现的单字换一个动画名，强制它从头播——容器级增删 class 不会重启动画
   *    （浏览器在帧末统一算样式，同任务内摘除再加回等于没变），实测无效。
   */
  function replayReveal(root) {
    if (!root || typeof window === "undefined") return;
    const targets = Array.from(root.querySelectorAll(".rv"));
    if (!targets.length) return;
    if (motionDisabled()) {
      targets.forEach((el) => el.classList.add("vis"));
      return;
    }

    targets.forEach((el) => el.classList.remove("vis"));
    replayCharAnimations(root);
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
    replayReveal,
    resetReveal,
    disconnect,
  };
}
