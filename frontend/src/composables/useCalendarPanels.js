import { onBeforeUnmount, onMounted, ref } from "vue";

import { GO_TOP_EVENT } from "../constants/events";

const DEFAULT_FLIP_LOCK_MS = 820;
const DEFAULT_WHEEL_THRESHOLD = 18;
const DEFAULT_TOUCH_THRESHOLD = 48;
const FORWARD_KEYS = ["ArrowDown", "ArrowRight", "PageDown", " "];
const BACKWARD_KEYS = ["ArrowUp", "ArrowLeft", "PageUp"];
const RESET_KEYS = ["Home", "Escape"];

function isInteractiveTarget(target) {
  if (!target) {
    return false;
  }

  if (typeof document !== "undefined" && target === document.body) {
    return false;
  }

  return Boolean(
    target.isContentEditable ||
      target.closest?.('a, button, input, textarea, select, summary, [role="button"], [role="link"]'),
  );
}

export function useCalendarPanels(
  panels,
  { initialPanel = "cover", flipLockMs = DEFAULT_FLIP_LOCK_MS } = {},
) {
  const activePanel = ref(initialPanel);
  const isFlipping = ref(false);
  const touchStartY = ref(0);
  let flipTimer = 0;

  function clearFlipTimer() {
    if (flipTimer && typeof window !== "undefined") {
      window.clearTimeout(flipTimer);
    }
    flipTimer = 0;
  }

  function startFlipLock() {
    isFlipping.value = true;
    clearFlipTimer();

    if (typeof window !== "undefined") {
      flipTimer = window.setTimeout(finishFlip, flipLockMs);
    }
  }

  function getActivePanelIndex() {
    const currentIndex = panels.indexOf(activePanel.value);
    return currentIndex >= 0 ? currentIndex : 0;
  }

  function getBoundedPanelIndex(index) {
    return Math.min(Math.max(index, 0), panels.length - 1);
  }

  function finishFlip() {
    isFlipping.value = false;
    clearFlipTimer();
  }

  function showPanel(panel) {
    if (!panels.includes(panel) || panel === activePanel.value || isFlipping.value) {
      return false;
    }

    activePanel.value = panel;
    startFlipLock();
    return true;
  }

  function movePanel(step) {
    const nextIndex = getBoundedPanelIndex(getActivePanelIndex() + step);
    return showPanel(panels[nextIndex]);
  }

  function resetToInitialPanel(options = {}) {
    const changed = activePanel.value !== initialPanel;
    const shouldLock = options?.lock !== false;

    clearFlipTimer();
    activePanel.value = initialPanel;

    if (changed && shouldLock) {
      startFlipLock();
    } else {
      isFlipping.value = false;
    }

    return changed;
  }

  function handleGoTopEvent() {
    resetToInitialPanel();
  }

  function handleWheel(event) {
    if (Math.abs(event.deltaY) <= DEFAULT_WHEEL_THRESHOLD) {
      return;
    }

    if (isFlipping.value) {
      event.preventDefault();
      return;
    }

    if (movePanel(event.deltaY > 0 ? 1 : -1)) {
      event.preventDefault();
    }
  }

  function handleKeydown(event) {
    if (isInteractiveTarget(event.target)) {
      return;
    }

    if (FORWARD_KEYS.includes(event.key)) {
      if (movePanel(1)) event.preventDefault();
      return;
    }

    if (BACKWARD_KEYS.includes(event.key)) {
      if (movePanel(-1)) event.preventDefault();
      return;
    }

    if (RESET_KEYS.includes(event.key) && activePanel.value !== initialPanel) {
      resetToInitialPanel();
      event.preventDefault();
    }
  }

  function handleTouchStart(event) {
    touchStartY.value = event.changedTouches?.[0]?.clientY || 0;
  }

  function handleTouchEnd(event) {
    const endY = event.changedTouches?.[0]?.clientY || 0;
    const deltaY = touchStartY.value - endY;
    touchStartY.value = 0;

    if (Math.abs(deltaY) < DEFAULT_TOUCH_THRESHOLD) {
      return;
    }

    if (isFlipping.value) {
      event.preventDefault();
      return;
    }

    if (movePanel(deltaY > 0 ? 1 : -1)) {
      event.preventDefault();
    }
  }

  onMounted(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.addEventListener(GO_TOP_EVENT, handleGoTopEvent);
  });

  onBeforeUnmount(() => {
    if (typeof window !== "undefined") {
      window.removeEventListener(GO_TOP_EVENT, handleGoTopEvent);
    }
    clearFlipTimer();
  });

  return {
    activePanel,
    isFlipping,
    showPanel,
    movePanel,
    resetToCover: resetToInitialPanel,
    finishFlip,
    handleWheel,
    handleKeydown,
    handleTouchStart,
    handleTouchEnd,
  };
}
