// 工作区模块：分栏比例、视图模式切换、专注模式与写作辅助（字数/大纲）。

import {
  markdownInput,
  outlineTarget,
  workspace,
  workspaceDivider,
  writingShell,
  writingStats,
} from "./dom.js";
import { escapeHtml } from "./util.js";
import { previewComputed } from "./preview.js";

function applyWorkspaceRatio(ratio) {
  if (!workspace || window.matchMedia("(max-width: 980px)").matches) return;
  const clamped = Math.min(70, Math.max(30, Number(ratio) || 50));
  workspace.style.gridTemplateColumns = `${clamped}% 10px calc(${100 - clamped}% - 10px)`;
  localStorage.setItem("admin:write-ratio", String(clamped));
  workspaceDivider?.setAttribute("aria-valuenow", String(Math.round(clamped)));
}

function preferredViewMode() {
  const stored = localStorage.getItem("admin:write-view");
  if (stored && ["write", "split", "preview"].includes(stored)) return stored;
  if (window.matchMedia("(max-width: 760px)").matches) return "write";
  if (window.matchMedia("(max-width: 1179px)").matches) return "write";
  return "split";
}

export function applyViewMode(mode) {
  if (!writingShell) return;
  let normalized = ["write", "split", "preview"].includes(mode) ? mode : "write";
  if (normalized === "split" && window.matchMedia("(max-width: 760px)").matches) normalized = "write";
  writingShell.dataset.view = normalized;
  localStorage.setItem("admin:write-view", normalized);
  document.querySelectorAll("[data-view-mode]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewMode === normalized);
    button.setAttribute("aria-pressed", button.dataset.viewMode === normalized ? "true" : "false");
  });
}

function updateWritingAssist() {
  const markdown = markdownInput?.value || "";
  const compact = markdown.replace(/\s+/g, "");
  const readTime = previewComputed.readTime || "1 min";
  if (writingStats) writingStats.textContent = `${compact.length} 字 · ${readTime}`;
  if (!outlineTarget) return;
  const headings = [];
  let offset = 0;
  markdown.split(/\r?\n/).forEach((line) => {
    const match = line.match(/^(##|###)\s+(.+)/);
    if (match) headings.push({ level: match[1].length, text: match[2].trim(), offset });
    offset += line.length + 1;
  });
  if (!headings.length) {
    outlineTarget.innerHTML = "<p>添加二级标题后会在这里生成目录。</p>";
    return;
  }
  outlineTarget.innerHTML = headings.map((item, index) => `
    <button type="button" data-outline-index="${index}" data-level="${item.level}">${escapeHtml(item.text)}</button>
  `).join("");
  outlineTarget.querySelectorAll("[data-outline-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = headings[Number(button.dataset.outlineIndex)];
      if (!item || !markdownInput) return;
      markdownInput.focus();
      markdownInput.setSelectionRange(item.offset, item.offset);
      const before = markdown.slice(0, item.offset);
      const lineCount = before.split("\n").length;
      markdownInput.scrollTop = Math.max(0, (lineCount - 3) * 25);
      document.getElementById("outline-panel").hidden = true;
    });
  });
}

export function initWorkspace() {
  applyWorkspaceRatio(localStorage.getItem("admin:write-ratio") || 50);
  workspaceDivider?.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    workspaceDivider.classList.add("is-dragging");
    workspaceDivider.setPointerCapture(event.pointerId);
  });
  workspaceDivider?.addEventListener("pointermove", (event) => {
    if (!workspaceDivider.hasPointerCapture(event.pointerId)) return;
    const bounds = workspace.getBoundingClientRect();
    applyWorkspaceRatio(((event.clientX - bounds.left) / bounds.width) * 100);
  });
  workspaceDivider?.addEventListener("pointerup", (event) => {
    workspaceDivider.classList.remove("is-dragging");
    if (workspaceDivider.hasPointerCapture(event.pointerId)) workspaceDivider.releasePointerCapture(event.pointerId);
  });
  workspaceDivider?.addEventListener("keydown", (event) => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    const current = Number(localStorage.getItem("admin:write-ratio") || 50);
    applyWorkspaceRatio(current + (event.key === 'ArrowLeft' ? -2 : 2));
  });

  document.querySelectorAll("[data-view-mode]").forEach((button) => {
    button.addEventListener("click", () => applyViewMode(button.dataset.viewMode));
  });
  applyViewMode(preferredViewMode());

  document.getElementById("focus-mode-button")?.addEventListener("click", (event) => {
    const enabled = document.body.classList.toggle("is-focus-mode");
    event.currentTarget.textContent = enabled ? "退出专注" : "专注";
    if (enabled) applyViewMode("write");
  });

  markdownInput?.addEventListener("input", updateWritingAssist);
  updateWritingAssist();
}
