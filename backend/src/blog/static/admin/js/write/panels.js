// 抽屉面板：打开/关闭、遮罩与焦点圈定。

import { drawerBackdrop } from "./dom.js";

let panelReturnFocus = null;

export function openPanel(panelId) {
  const panel = document.getElementById(panelId);
  if (!panel) return;
  if (panel.hidden && document.activeElement instanceof HTMLElement) panelReturnFocus = document.activeElement;
  document.querySelectorAll(".author-drawer:not([hidden])").forEach((item) => {
    if (item !== panel) item.hidden = true;
  });
  panel.hidden = false;
  if (drawerBackdrop) drawerBackdrop.hidden = false;
  const focusable = panel.querySelector("input, textarea, button, select, [tabindex]");
  window.setTimeout(() => focusable?.focus(), 0);
}

export function closePanel(panelId, { restoreFocus = true } = {}) {
  const panel = document.getElementById(panelId);
  if (panel) panel.hidden = true;
  if (drawerBackdrop && !document.querySelector(".author-drawer:not([hidden])")) drawerBackdrop.hidden = true;
  if (restoreFocus && panelReturnFocus?.isConnected) window.setTimeout(() => panelReturnFocus.focus(), 0);
}

export function closeAllPanels() {
  document.querySelectorAll(".author-drawer:not([hidden])").forEach((panel) => { panel.hidden = true; });
  if (drawerBackdrop) drawerBackdrop.hidden = true;
  if (panelReturnFocus?.isConnected) window.setTimeout(() => panelReturnFocus.focus(), 0);
}

export function initPanels() {
  document.addEventListener("click", (event) => {
    const toggle = event.target.closest("[data-toggle-panel]");
    if (toggle) {
      toggle.closest("details")?.removeAttribute("open");
      const panelId = toggle.dataset.togglePanel;
      const panel = document.getElementById(panelId);
      if (panel?.classList.contains("outline-panel")) panel.hidden = !panel.hidden;
      else openPanel(panelId);
      return;
    }
    const closer = event.target.closest("[data-close-panel]");
    if (closer) closePanel(closer.dataset.closePanel);
  });
  drawerBackdrop?.addEventListener("click", closeAllPanels);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { closeAllPanels(); return; }
    if (event.key !== "Tab") return;
    const panel = document.querySelector(".author-drawer:not([hidden])");
    if (!panel) return;
    const focusable = Array.from(panel.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])')).filter((node) => !node.hidden);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}
