<script setup>
/**
 * 首页版次轨道：固定在右缘，标示 首页 / 最近 / 热点 三版并支持直接跳转。
 * 仅在整屏翻页模式（首页）下出现；矮屏/窄屏隐藏，避免与桌宠、报头挤压。
 */
import { usePageFlip } from "../../composables/usePageFlip";

const PAGES = [
  { index: 0, label: "首页", name: "封面" },
  { index: 1, label: "最近", name: "最近更新" },
  { index: 2, label: "热点", name: "热点文章" },
];

const { currentPage, isFlipActive, goToPage } = usePageFlip();
</script>

<template>
  <Transition name="rail-fade">
    <nav v-if="isFlipActive" class="home-page-rail" aria-label="首页版次导航">
      <ol class="rail-list">
        <li v-for="page in PAGES" :key="page.index" class="rail-item">
          <button
            type="button"
            class="rail-button"
            :class="{ 'is-current': currentPage === page.index }"
            :aria-current="currentPage === page.index ? 'true' : undefined"
            :aria-label="`第 ${page.index + 1} 版 · ${page.name}`"
            :title="page.name"
            @click="goToPage(page.index)"
          >
            <span class="rail-button__tick" aria-hidden="true"></span>
            <span class="rail-button__label" aria-hidden="true">{{ page.label }}</span>
          </button>
        </li>
      </ol>
    </nav>
  </Transition>
</template>

<style scoped>
.home-page-rail {
  position: fixed;
  top: 50%;
  right: clamp(0.75rem, 1.8vw, 1.5rem);
  z-index: 1150;
  transform: translateY(-50%);
  /* 轨道本体不吃指针事件，只有按钮可点，避免遮挡正文 */
  pointer-events: none;
}

.rail-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.1rem;
  border-right: 1px solid var(--rule-light, rgba(42, 36, 28, 0.18));
}

.rail-item {
  display: flex;
  justify-content: flex-end;
}

.rail-button {
  pointer-events: auto;
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.45rem;
  padding: 0.34rem 0.55rem 0.34rem 0;
  border: 0;
  background: transparent;
  color: var(--ink-faded, #8a7f6f);
  cursor: pointer;
  font-family: var(--f-mono, monospace);
  font-size: 0.56rem;
  letter-spacing: 0.16em;
  transition: color 0.25s ease;
}

/* 刻度线的布局盒固定 26px，只让线本身在盒内右对齐伸缩——
   这样三个按钮的标签始终对齐，轨道总宽也不随悬停变化（恒定约 84px）。 */
.rail-button__tick {
  width: 26px;
  height: 1px;
  background-image: linear-gradient(currentColor, currentColor);
  background-repeat: no-repeat;
  background-position: right center;
  background-size: 11px 1px;
  transition: background-size 0.32s var(--ease-quart, cubic-bezier(0.25, 1, 0.5, 1));
}

/* 标签由 001/002/003 改为「首页/最近/热点」：中文在 0.56rem 下笔画会糊，
   放宽一档并收掉给数字排字设计的字距。 */
.rail-button__label {
  font-size: 0.64rem;
  letter-spacing: 0.08em;
}

/* 版名不做可见展开：展开会在悬停时把轨道向左撑进正文，压住榜单行尾的阅读量。
   轨道宽度因此恒定，右侧安全边只需按这个固定宽度预留。
   版名改由 title 提示与 aria-label 承担。 */
.rail-button:hover {
  color: var(--ink-mid, #3b3328);
}

.rail-button:hover .rail-button__tick {
  background-size: 17px 1px;
}

.rail-button.is-current {
  color: var(--accent, #8b2500);
}

.rail-button.is-current .rail-button__tick {
  background-size: 26px 1px;
}

.rail-button.is-current .rail-button__label {
  font-weight: 700;
}

/* Tab 进入时给一个克制的焦点环（默认 outline 被全局 reset 掉了） */
.rail-button:focus-visible {
  outline: 1px solid var(--accent, #8b2500);
  outline-offset: 1px;
}

.rail-fade-enter-active,
.rail-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.rail-fade-enter-from,
.rail-fade-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(8px);
}

@media (max-width: 900px), (max-height: 560px) {
  .home-page-rail {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  html:not(.app-ready) .rail-button,
  html:not(.app-ready) .rail-button__tick,
  html:not(.app-ready) .rail-fade-enter-active,
  html:not(.app-ready) .rail-fade-leave-active {
    transition: none;
  }
}
</style>
