// 文章页双侧栏折叠状态（模块级单例）。
// 左栏（栏目文章目录）可整栏收进左边，右栏（本文目录批注栏）可收进右边；
// 各自有一条书脊式固定页签提供重新打开。均为会话内状态：
// 离开文章页时由 App.vue 统一复位，避免读者忘了开着折叠忘了找。

import { ref } from "vue";

export const railCollapsed = ref(false);
export const sideCollapsed = ref(false);

export function useDeskPanels() {
  function toggleRail(collapsed = !railCollapsed.value) {
    railCollapsed.value = collapsed;
  }

  function toggleSide(collapsed = !sideCollapsed.value) {
    sideCollapsed.value = collapsed;
  }

  function resetPanels() {
    railCollapsed.value = false;
    sideCollapsed.value = false;
  }

  return { railCollapsed, sideCollapsed, toggleRail, toggleSide, resetPanels };
}
