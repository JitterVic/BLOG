import { nextTick, onMounted, onUnmounted, watch } from "vue";
import { useRoute } from "vue-router";

const DEFAULT_SELECTOR = ".rv:not(.vis)";
const DEFAULT_ROOT_MARGIN = "0px 0px -6% 0px";
const DEFAULT_THRESHOLD = 0.08;
const SAFETY_REVEAL_MS = 1600;

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
  }

  function markVisible(el) {
    if (!el || el.classList.contains("vis")) return;
    const delay = Number(el.dataset.revealDelay ?? staggerIndex * staggerMs);
    el.style.setProperty("--reveal-delay", `${delay}ms`);
    staggerIndex += 1;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.classList.add("vis");
      });
    });
  }

  function observeTargets() {
    const host = getRoot();
    if (!host || typeof window === "undefined") return;

    if (prefersReducedMotion()) {
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
    clearSafety();
    safetyTimer = window.setTimeout(() => {
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
    disconnect,
  };
}