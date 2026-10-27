import { onScopeDispose, ref } from "vue";

import { getNotes, isRequestAbort } from "../services/api";

export const NOTE_TYPES = [
  { value: "", label: "全部" },
  { value: "daily", label: "日常" },
  { value: "project", label: "项目" },
  { value: "work", label: "作品" },
  { value: "thought", label: "随想" },
];

export function useNotes() {
  const notes = ref([]);
  const total = ref(0);
  const error = ref("");
  const loading = ref(false);
  let controller = null;
  let sequence = 0;

  async function loadNotes({ type = "", limit = 20, page = 1 } = {}) {
    const requestId = ++sequence;
    controller?.abort();
    controller = new AbortController();
    loading.value = true;
    error.value = "";
    try {
      const result = await getNotes({ type, limit, page, signal: controller.signal });
      if (requestId !== sequence) return [];
      notes.value = Array.isArray(result?.items) ? result.items : [];
      total.value = Number(result?.total) || notes.value.length;
      return notes.value;
    } catch (err) {
      if (requestId === sequence && !isRequestAbort(err)) {
        error.value = err?.code === "NETWORK_ERROR"
          ? "余笺暂时无法加载，请检查网络后重试。"
          : "余笺加载失败，请稍后重试。";
        notes.value = [];
      }
      return [];
    } finally {
      if (requestId === sequence) loading.value = false;
    }
  }

  onScopeDispose(() => controller?.abort());

  return { notes, total, error, loading, loadNotes };
}