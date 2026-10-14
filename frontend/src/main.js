import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import { MOTION_STORAGE_KEY, applyMotionClass, motionDisabled } from "./composables/useReveal";
import "./styles.css";

const frontendBuild = "pencil-trail-v2";
document.documentElement.dataset.frontendBuild = frontendBuild;
console.info(`[BLOG] frontend build: ${frontendBuild}`);

// 用户显式关闭动效时，在根元素打标记：CSS 里那些只靠媒体查询判定的
// `@media (prefers-reduced-motion: reduce)` 规则读不到 localStorage，
// 用 `motion-off` / `motion-on` 这对类把同一套降级样式在手动覆盖下也生效
// （见 feedback.css 等文件的 `html:not(.motion-on)` 兜底）。
// 放在挂载之前设置，避免首屏先播出动画再被切换掉。
applyMotionClass(
  (() => {
    try {
      const stored = window.localStorage.getItem(MOTION_STORAGE_KEY);
      if (stored === "off") return true;
      if (stored === "on") return false;
    } catch {
      // 隐私模式下 localStorage 不可用，跟随系统偏好即可。
    }
    return motionDisabled();
  })(),
);

createApp(App).use(router).mount("#app");

