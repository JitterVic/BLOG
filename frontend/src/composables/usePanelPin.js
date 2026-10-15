// 侧栏面板的纵向吸附：自己算位置，而不是交给 position: sticky。
//
// 交给 sticky 时，面板被夹在它所在那条网格区域的纵向范围里。区域的高度由正文决定
// （清单本身不参与行高计算，目录又比正文矮），于是短文下面板只被钉住两百多像素：
// 区域一滚过去，面板就被夹到区域底部随之上滑，头部那枚收起/展开按钮先滑到固定顶栏
// 底下、再滑出屏幕——表现就是「收回了就打不开」。实测一篇 217px 的短文在 700px 高的
// 窗口里，面板顶部会一路滑到 -193。
//
// 所以这里自己算：面板钉在吸附线上不动，可用高度随「区域末端」收缩，区域走完即整体
// 隐去。这样纵向位置从滚进阅读区到正文读完都是稳定的，既不会滑出屏幕，也不会多出
// 空白（面板不会越过区域末端，因此不会压到正文之后的内容）。

import { onBeforeUnmount, onMounted, ref } from "vue";

// 低于这个高度就不再显示：此时区域已到末尾，留一条几十像素的碎片只会让人误点。
const MIN_VISIBLE_PX = 96;
const VIEWPORT_MARGIN_PX = 8;

export function usePanelPin(hostRef, { pinRem = 6.8, anchor = ".post-reading-layout" } = {}) {
  const shift = ref(0);
  const parked = ref(false);

  function sync() {
    const host = hostRef.value;
    const region = host?.closest(anchor);
    if (!host || !region) return;

    const rootPx = Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const pin = pinRem * rootPx;
    const rect = region.getBoundingClientRect();

    // 区域顶端还在吸附线以下时跟着它走，越过吸附线之后就钉住不动。
    const top = Math.max(rect.top, pin);
    const room = Math.min(window.innerHeight - top - VIEWPORT_MARGIN_PX, rect.bottom - top);

    host.style.setProperty("--panel-shift", `${Math.round(top - rect.top)}px`);
    host.style.setProperty("--panel-avail", `${Math.round(Math.max(MIN_VISIBLE_PX, room))}px`);
    shift.value = Math.round(top - rect.top);
    parked.value = room < MIN_VISIBLE_PX;
  }

  onMounted(() => {
    window.addEventListener("scroll", sync, { passive: true });
    window.addEventListener("resize", sync, { passive: true });
    sync();
  });

  onBeforeUnmount(() => {
    window.removeEventListener("scroll", sync);
    window.removeEventListener("resize", sync);
  });

  return { shift, parked, sync };
}
