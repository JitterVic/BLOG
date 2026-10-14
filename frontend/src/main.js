import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "./styles.css";

const frontendBuild = "pencil-trail-v2";
document.documentElement.dataset.frontendBuild = frontendBuild;
console.info(`[BLOG] frontend build: ${frontendBuild}`);

// 入场动效默认开启：本站以视觉呈现为主，动效是版式的一部分，
// 因此不再根据 `prefers-reduced-motion` 关闭它（媒体查询仍保留在 CSS 里，
// 供系统开启「减弱动态效果」时做兜底降级，但应用层不会主动去关）。
// 标记应用已接管：CSS 里 `@media (prefers-reduced-motion: reduce)` 的兜底降级
// 只对 `html:not(.app-ready)` 生效。本站以视觉呈现为主，动效属于版式的一部分，
// 挂载后即按站点设计正常播放，不再被系统开关整站抹平。
document.documentElement.classList.add("app-ready");

createApp(App).use(router).mount("#app");

