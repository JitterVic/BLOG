import { onBeforeUnmount, watch } from "vue";

const DEFAULT_DESCRIPTION = "至知：记录技术实践、项目复盘和长期学习的个人博客。";

function getDescriptionElement() {
  let element = document.querySelector('meta[name="description"]');
  if (!element) {
    element = document.createElement("meta");
    element.name = "description";
    document.head.appendChild(element);
  }
  return element;
}

export function setPageMeta({ title = "至知", description = DEFAULT_DESCRIPTION } = {}) {
  if (typeof document === "undefined") return;
  document.title = title;
  getDescriptionElement().setAttribute("content", description || DEFAULT_DESCRIPTION);
}

export function usePageMeta(source) {
  const stop = watch(source, (meta) => setPageMeta(meta), { immediate: true });
  onBeforeUnmount(stop);
  return { setPageMeta };
}
