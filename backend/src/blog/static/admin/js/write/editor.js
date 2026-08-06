// 编辑器操作：选区替换、块插入、工具栏命令与快捷键。

import { markdownInput, toolbar } from "./dom.js";

export function dispatchEditorInput() {
  markdownInput?.dispatchEvent(new Event("input", { bubbles: true }));
}

export function replaceSelection(before, after = before, placeholder = "") {
  if (!markdownInput) return;
  const start = markdownInput.selectionStart;
  const end = markdownInput.selectionEnd;
  const selected = markdownInput.value.slice(start, end) || placeholder;
  markdownInput.setRangeText(`${before}${selected}${after}`, start, end, "end");
  markdownInput.focus();
  const cursorStart = start + before.length;
  markdownInput.setSelectionRange(cursorStart, cursorStart + selected.length);
  dispatchEditorInput();
}

export function prefixSelectedLines(prefix) {
  if (!markdownInput) return;
  const start = markdownInput.selectionStart;
  const end = markdownInput.selectionEnd;
  const lineStart = markdownInput.value.lastIndexOf("\n", start - 1) + 1;
  const nextBreak = markdownInput.value.indexOf("\n", end);
  const lineEnd = nextBreak === -1 ? markdownInput.value.length : nextBreak;
  const selected = markdownInput.value.slice(lineStart, lineEnd);
  const replacement = selected.split("\n").map((line) => `${prefix}${line}`).join("\n");
  markdownInput.setRangeText(replacement, lineStart, lineEnd, "select");
  markdownInput.focus();
  dispatchEditorInput();
}

export function insertBlock(content) {
  if (!markdownInput) return;
  const start = markdownInput.selectionStart;
  const paddingBefore = start > 0 && !markdownInput.value.slice(0, start).endsWith("\n\n") ? "\n\n" : "";
  const paddingAfter = markdownInput.value.slice(markdownInput.selectionEnd).startsWith("\n") ? "" : "\n";
  markdownInput.setRangeText(`${paddingBefore}${content}${paddingAfter}`, start, markdownInput.selectionEnd, "end");
  markdownInput.focus();
  dispatchEditorInput();
}

export function insertAtCursor(text) {
  if (!markdownInput) return;
  const start = markdownInput.selectionStart;
  const end = markdownInput.selectionEnd;
  markdownInput.setRangeText(text, start, end, "end");
  markdownInput.focus();
  dispatchEditorInput();
}

export function replaceUploadPlaceholder(anchor, replacement) {
  if (!markdownInput) return;
  const scrollTop = markdownInput.scrollTop;
  let position = anchor.start;
  if (markdownInput.value.slice(position, position + anchor.placeholder.length) !== anchor.placeholder) {
    position = markdownInput.value.indexOf(anchor.placeholder);
  }
  if (position < 0) {
    position = Math.min(anchor.start, markdownInput.value.length);
    markdownInput.setRangeText(replacement, position, position, "end");
  } else {
    markdownInput.setRangeText(replacement, position, position + anchor.placeholder.length, "end");
  }
  markdownInput.scrollTop = scrollTop;
  markdownInput.focus();
  markdownInput.setSelectionRange(position + replacement.length, position + replacement.length);
  dispatchEditorInput();
}

export function runCommand(command) {
  const commands = {
    bold: () => replaceSelection("**", "**", "粗体文字"),
    italic: () => replaceSelection("*", "*", "斜体文字"),
    h2: () => prefixSelectedLines("## "),
    h3: () => prefixSelectedLines("### "),
    quote: () => prefixSelectedLines("> "),
    code: () => insertBlock("```text\n在这里输入代码\n```"),
    link: () => replaceSelection("[", "](https://)", "链接文字"),
    image: () => replaceSelection("![", "](/uploads/media/)", "alt"),
    table: () => insertBlock("| 列 1 | 列 2 |\n| --- | --- |\n| 内容 | 内容 |"),
  };
  commands[command]?.();
}

export function initToolbar() {
  toolbar?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-command]");
    if (button) runCommand(button.dataset.command);
  });

  markdownInput?.addEventListener("keydown", (event) => {
    const modifier = event.ctrlKey || event.metaKey;
    if (modifier && ["b", "i", "k"].includes(event.key.toLowerCase())) {
      event.preventDefault();
      runCommand({ b: "bold", i: "italic", k: "link" }[event.key.toLowerCase()]);
      return;
    }
    if (event.key === "Tab") {
      event.preventDefault();
      if (markdownInput.selectionStart !== markdownInput.selectionEnd) prefixSelectedLines("  ");
      else replaceSelection("  ", "", "");
    }
  });
}
