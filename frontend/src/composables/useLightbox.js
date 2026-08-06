// 图片灯箱：管理 dialog 打开/关闭与当前预览图片状态。

import { ref } from "vue";

export function useLightbox() {
  const dialogRef = ref(null);
  const lightboxImage = ref({ src: "", alt: "" });

  function dialogElement() {
    const target = dialogRef.value;
    return target?.$el || target;
  }

  function open(image) {
    lightboxImage.value = {
      src: image.currentSrc || image.src,
      alt: image.alt || "文章图片",
    };
    const dialog = dialogElement();
    if (!dialog) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function close() {
    const dialog = dialogElement();
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function handleBackdropClick(event) {
    if (event.target === dialogElement()) close();
  }

  return { dialogRef, lightboxImage, open, close, handleBackdropClick };
}
