// 面板折叠状态：文章页会在换篇时整体重建组件，刷新后也要保留，
// 因此偏好读写 localStorage 而不是留在组件里。

import { ref } from "vue";

function readStored(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    // 隐私模式读不到：按默认展开处理。
    return null;
  }
}

function writeStored(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // 写不进去只影响「下次是否记得」，不该打断阅读。
  }
}

export function usePersistedCollapse(key, { defaultCollapsed = false } = {}) {
  const stored = typeof window === "undefined" ? null : readStored(key);
  // setup 期就定稿：先按默认值渲染再在 onMounted 里收起，能看见一次展开闪动。
  const collapsed = ref(stored === null ? defaultCollapsed : stored === "1");

  function setCollapsed(value) {
    collapsed.value = Boolean(value);
    writeStored(key, collapsed.value ? "1" : "0");
  }

  return {
    collapsed,
    collapse: () => setCollapsed(true),
    expand: () => setCollapsed(false),
    toggle: () => setCollapsed(!collapsed.value),
  };
}
