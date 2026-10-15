// 左侧清单的高度上限：由正文实际高度推导。
//
// 清单是阅读版式的网格项，它的盒高会参与那一行的高度计算。只按视口封顶（34rem）
// 还不够：一篇只有一段的短文配 30 条清单，会在正文之后空出几百像素只有左栏的留白
// （实测 327px，读者要滚过一整片空白才够得着上下篇与相关文章），而且折叠清单时
// 整页高度骤降，浏览器会把滚动位置夹回去。
//
// 因此上限取「正文高度」「可用视口」「绝对封顶」三者的最小值，再压一个很小的下限。

import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const MIN_PX = 160; // 10rem：低于此值连年份分组都看不全，但取值必须足够小，
// 免得它比正文还高——那正是「折叠侧栏时页脚高度骤降」的残留来源
const CAP_PX = 544; // 34rem，与 post.css 的兜底封顶一致
const VIEWPORT_GAP_PX = 136; // 8.5rem：顶栏与吸附位置的占位

/** 正文元素既可能以模板 ref 传入（在 <script setup> 里会被自动解包成元素），
    也可能以元素本身传入，两种都接住。 */
function resolveElement(source) {
  const value = source && typeof source === "object" && "value" in source ? source.value : source;
  return value instanceof Element ? value : null;
}

export function useRailHeight(bodySource, enabled) {
  const railMaxHeight = ref(null);
  let observer = null;

  function measure() {
    if (enabled && !enabled.value) {
      railMaxHeight.value = null;
      return;
    }
    const available = Math.max(MIN_PX, window.innerHeight - VIEWPORT_GAP_PX);
    const bodyHeight = resolveElement(bodySource)?.offsetHeight || available;
    railMaxHeight.value = Math.round(Math.max(MIN_PX, Math.min(bodyHeight, available, CAP_PX)));
  }

  function disconnect() {
    observer?.disconnect();
    observer = null;
  }

  function connect() {
    disconnect();
    const body = resolveElement(bodySource);
    if (!body || (enabled && !enabled.value) || typeof ResizeObserver === "undefined") return;
    observer = new ResizeObserver(measure);
    observer.observe(body);
  }

  function refresh() {
    measure();
    connect();
  }

  onMounted(() => {
    refresh();
    window.addEventListener("resize", measure, { passive: true });
  });

  watch([() => resolveElement(bodySource), enabled], refresh, { flush: "post" });

  onBeforeUnmount(() => {
    disconnect();
    window.removeEventListener("resize", measure);
  });

  return { railMaxHeight };
}
