// 导入模块：外部 Markdown 文件解析导入与状态提示。

import {
  categoryInput,
  coverImageInput,
  excerptInput,
  heroQuoteInput,
  importWarning,
  markdownFileInput,
  markdownInput,
  publishedAtInput,
  readTimeInput,
  slugInput,
  tagsInput,
  titleInput,
} from "./dom.js";
import { fetchJson } from "./api.js";
import { setSaveState } from "./save-state.js";
import { normalizeDateInput } from "./util.js";
import { dispatchEditorInput } from "./editor.js";
import { updateFrontPreview } from "./preview.js";
import { saveLocalDraft, scheduleDraftPersistence } from "./autosave.js";
import { showRetryAutosave } from "./autosave.js";
import { updateSlugHint } from "./publish.js";

function showImportWarning(markdownContent = "") {
  if (!importWarning) return;
  const references = markdownContent.match(/!\[[^\]]*\]\((?:\.{1,2}\/)[^)]+\)/g) || [];
  importWarning.hidden = references.length === 0;
  importWarning.textContent = references.length
    ? `检测到 ${references.length} 张本地图片引用，请上传替换。`
    : "";
}

function showImportStatus(message = "", isError = false) {
  if (!importWarning) return;
  if (!message) {
    importWarning.hidden = true;
    importWarning.textContent = "";
    importWarning.classList.remove("is-error", "is-success");
    return;
  }
  importWarning.hidden = false;
  importWarning.textContent = message;
  importWarning.classList.toggle("is-error", isError);
  importWarning.classList.toggle("is-success", !isError);
}

export async function importMarkdownFile(file) {
  if (!file) return;
  const importUrl = document.body?.dataset?.importUrl;
  if (!importUrl) {
    setSaveState("error", "导入地址不可用，请刷新页面后重试。");
    showImportStatus("导入地址不可用，请刷新页面后重试。", true);
    return;
  }
  if (!/\.(?:md|markdown|txt)$/i.test(file.name || "")) {
    const message = "请选择 .md / .markdown 文稿文件（也兼容 .txt）。";
    setSaveState("error", message);
    showImportStatus(message, true);
    return;
  }
  if (markdownInput?.value.trim() && !window.confirm("编辑器中已有正文，导入 Markdown 会覆盖现有内容。确定继续吗？")) {
    return;
  }
  const formData = new FormData();
  formData.append("markdown_file", file);
  try {
    setSaveState("syncing", `正在导入 ${file.name || "Markdown"}……`);
    showImportStatus(`正在导入 ${file.name || "Markdown"}……`, false);
    const data = await fetchJson(importUrl, { method: "POST", body: formData });
    if (markdownInput) markdownInput.value = data.markdown_content || "";
    if (titleInput) titleInput.value = data.title || "";
    if (slugInput) {
      slugInput.value = data.slug || "";
      updateSlugHint();
    }
    if (categoryInput) categoryInput.value = data.category || "";
    if (publishedAtInput) publishedAtInput.value = normalizeDateInput(data.published_at || "");
    if (tagsInput) {
      tagsInput.value = data.tags_text || (Array.isArray(data.tags) ? data.tags.join(", ") : "");
    }
    if (excerptInput) excerptInput.value = data.excerpt || "";
    if (readTimeInput) readTimeInput.value = data.read_time || "";
    if (heroQuoteInput) heroQuoteInput.value = data.hero_quote || "";
    if (coverImageInput) coverImageInput.value = data.cover_image || "";
    showImportWarning(markdownInput?.value || "");
    showImportStatus(`已导入 ${file.name || "Markdown"}。若封面是相对路径，请改为 /uploads/ 或 http(s) 地址后再发布。`, false);
    dispatchEditorInput();
    updateFrontPreview();
    saveLocalDraft({ announce: false });
    scheduleDraftPersistence();
    setSaveState("local", "文稿已导入到编辑器（尚未发布）");
  } catch (error) {
    const message = error.message || "导入失败";
    setSaveState("error", message);
    showImportStatus(message, true);
    showRetryAutosave(false);
  }
}

export function initImporter() {
  markdownFileInput?.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    await importMarkdownFile(file);
    event.target.value = "";
  });
}
