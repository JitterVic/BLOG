// 响应式 matchMedia。
//
// 断点在这里决定的不是样式，而是「要不要渲染、要不要发请求」——所以必须随视口
// 变化实时更新，不能用一次性求值。

import { onBeforeUnmount, onMounted, ref } from "vue";

export function useMediaQuery(query) {
  const mediaQuery =
    typeof window !== "undefined" && typeof window.matchMedia === "function"
      ? window.matchMedia(query)
      : null;
  const matches = ref(Boolean(mediaQuery?.matches));

  function sync(event) {
    matches.value = event.matches;
  }

  onMounted(() => {
    if (!mediaQuery) return;
    matches.value = mediaQuery.matches;
    mediaQuery.addEventListener("change", sync);
  });

  onBeforeUnmount(() => {
    mediaQuery?.removeEventListener("change", sync);
  });

  return matches;
}
