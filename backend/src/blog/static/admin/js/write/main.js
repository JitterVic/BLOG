// 写作台装配入口：按原始初始化顺序组合各功能模块。

import { postForm, publishTrigger, titleInput } from "./dom.js";
import { initToolbar } from "./editor.js";
import { initWorkspace } from "./workspace.js";
import { initImporter, importMarkdownFile } from "./importer.js";
import { initMedia } from "./media.js";
import { initPreview } from "./preview.js";
import {
  cancelPendingSaveTimers,
  currentPostId,
  initAutosave,
  persistDraftToServer,
  saveLocalDraft,
} from "./autosave.js";
import { initPanels } from "./panels.js";
import { initPublish } from "./publish.js";
import { initRevisions } from "./revisions.js";

initToolbar();
initWorkspace();
initImporter();
initMedia({ onDropMarkdownFile: importMarkdownFile });
initPreview();
initAutosave();
initPanels();
initPublish();
initRevisions();

document.addEventListener("keydown", (event) => {
  const modifier = event.ctrlKey || event.metaKey;
  if (!modifier) return;
  if (event.key.toLowerCase() === "s") {
    event.preventDefault();
    cancelPendingSaveTimers();
    saveLocalDraft({ announce: false });
    persistDraftToServer();
  }
  if (event.key === "Enter") {
    event.preventDefault();
    if (publishTrigger && !publishTrigger.disabled) postForm?.requestSubmit(publishTrigger);
  }
});

if (!currentPostId() && !titleInput?.value.trim()) {
  window.setTimeout(() => titleInput?.focus(), 0);
}
