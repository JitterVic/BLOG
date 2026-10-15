// 侧栏面板的纵向吸附：吸附态交给 position: fixed，脚本只负责「什么时候吸附」。
//
// 不能每帧写 top。面板是文档流里的绝对定位元素，滚动时浏览器先把它当普通内容一起滚
// 上去，主线程之后才派发 scroll 事件、脚本再把 top 补回来，这一来一回必然差一帧：
// 实测按 55px/帧 滚动时面板顶部稳定停在 53px，而吸附线在 108.8px——偏差正好等于一帧
// 的滚动量，而且不收敛；滚动越快偏得越远，看上去就是面板一直在抖、跟不上正文。
// fixed 元素完全不参与滚动，位置恒定；脚本只在跨过吸附线那一刻切一次类名，滚动过程
// 中一行都不跑。
//
// 也不能交给 position: sticky。它被夹在网格区域的纵向范围里，而区域高度由正文决定
// （清单不参与行高计算，目录又比正文矮），短文下面板只被钉住两百多像素，随后连同
// 收起/展开按钮一起被顶出屏幕——实测一篇 217px 的短文在 700px 高的窗口里，面板顶部
// 会一路滑到 -193，表现就是「收起来就打不开」。
//
// 于是纵向分成三段：吸附前贴着区域顶端随正文滚（脚本不写任何坐标）；越过吸附线后由
// .is-pinned 换成 fixed、钉在吸附线上；区域内剩余高度不足时整体隐去（is-parked），
// 免得留一条几十像素的碎片让人误点。

import { onBeforeUnmount, onMounted, ref } from "vue";

// 低于这个高度就不再显示：此时区域已到末尾，留一条碎片只会让人误点。
const MIN_VISIBLE_PX = 96;
const VIEWPORT_MARGIN_PX = 8;

export function usePanelPin(hostRef, { pinRem = 6.8, anchor = ".post-reading-layout" } = {}) {
  const pinned = ref(false);
  const parked = ref(false);

  let rootPx = 16;
  let lastAvail = 0;

  // 吸附线以 rem 计，但 fixed 的 top 必须是 px：写进 --panel-pin 供 CSS 使用，
  // 也留一份 px 给这里的可用高度计算，避免两边各写一份常量。
  function syncPinLine() {
    rootPx = Number.parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    hostRef.value?.style.setProperty("--panel-pin", `${Math.round(pinRem * rootPx)}px`);
  }

  function sync() {
    const host = hostRef.value;
    const region = host?.closest(anchor);
    if (!host || !region) return;

    const pin = pinRem * rootPx;
    const rect = region.getBoundingClientRect();

    // 区域顶端越过吸附线之前，面板贴在区域顶端（top: 0，跟着正文滚）；越过之后改为
    // 固定吸附。两种状态下算出来的位置在切换点重合，所以切换本身看不出跳变。
    const isPinned = rect.top <= pin;
    const top = isPinned ? pin : rect.top;
    const room = Math.min(window.innerHeight - top - VIEWPORT_MARGIN_PX, rect.bottom - top);
    const avail = Math.round(Math.max(MIN_VISIBLE_PX, room));

    // 只在数值真的变了才写：无事发生的帧不产生任何样式改写。
    if (avail !== lastAvail) {
      host.style.setProperty("--panel-avail", `${avail}px`);
      lastAvail = avail;
    }
    pinned.value = isPinned;
    parked.value = room < MIN_VISIBLE_PX;
  }

  function handleResize() {
    syncPinLine();
    sync();
  }

  onMounted(() => {
    syncPinLine();
    window.addEventListener("scroll", sync, { passive: true });
    window.addEventListener("resize", handleResize, { passive: true });
    sync();
  });

  onBeforeUnmount(() => {
    window.removeEventListener("scroll", sync);
    window.removeEventListener("resize", handleResize);
  });

  return { pinned, parked, sync };
}
