// 主题切换（DESIGN.md §4.5）：三态循环「跟随系统 → 浅 → 深」。
// 持久化键 zhizhi:theme；index.html 的内联脚本已在读到偏好时预置 data-theme，
// 这里只负责应用与切换。切换瞬时完成，不做过渡。

import { computed, ref, watch } from "vue";

const STORAGE_KEY = "zhizhi:theme";
const ORDER = ["", "light", "dark"];
const LABELS = {
  "": "跟随系统",
  light: "浅色",
  dark: "深色",
};

function readSaved() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved === "light" || saved === "dark" ? saved : "";
  } catch {
    return "";
  }
}

function persist(value) {
  try {
    if (value) localStorage.setItem(STORAGE_KEY, value);
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* 隐私模式下仅本次会话生效 */
  }
}

const mode = ref(readSaved());

watch(
  mode,
  (value) => {
    const root = document.documentElement;
    if (value) root.dataset.theme = value;
    else delete root.dataset.theme;
    persist(value);
  },
  { immediate: true },
);

export function useTheme() {
  const label = computed(() => LABELS[mode.value]);

  function cycle() {
    mode.value = ORDER[(ORDER.indexOf(mode.value) + 1) % ORDER.length];
  }

  return { mode, label, cycle };
}
