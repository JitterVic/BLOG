import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";
import "./styles.css";

const frontendBuild = "pencil-trail-v2";
document.documentElement.dataset.frontendBuild = frontendBuild;
console.info(`[BLOG] frontend build: ${frontendBuild}`);

createApp(App).use(router).mount("#app");

