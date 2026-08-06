// 保存状态指示：命令栏上的同步状态灯与文案。

import { autosaveStatus, saveState } from "./dom.js";

const SAVE_STATE_LABELS = {
  pristine: "未修改",
  local: "本地已保存",
  syncing: "正在同步",
  server: "服务器已保存",
  error: "同步失败",
};
const SAVE_STATE_CLASSES = ["is-pristine", "is-local", "is-syncing", "is-server", "is-error", "is-working", "is-saved"];

export function setSaveState(state, detail = "") {
  if (autosaveStatus) autosaveStatus.textContent = detail || SAVE_STATE_LABELS[state] || state;
  if (!saveState) return;
  saveState.classList.remove(...SAVE_STATE_CLASSES);
  const className = state === "working" ? "is-syncing" : state === "saved" ? "is-server" : `is-${state}`;
  saveState.classList.add(className);
}
