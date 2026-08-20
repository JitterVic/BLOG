<script setup>
defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  text: {
    type: String,
    default: "",
  },
  tag: {
    type: String,
    default: "日常",
  },
  statusText: {
    type: String,
    default: "伴读中",
  },
  isSoundOn: {
    type: Boolean,
    default: false,
  },
  hasCustomPosition: {
    type: Boolean,
    default: false,
  },
});

defineEmits([
  "close",
  "launch",
  "toggle-sound",
  "poke",
  "reset-pos",
]);
</script>

<template>
  <Transition name="bubble-pop">
    <div v-if="visible" class="cat-speech-bubble" role="tooltip" aria-live="polite">
      <!-- 气泡尖角 -->
      <div class="bubble-tail"></div>

      <!-- 气泡头部：标签 + 状态 + 关闭 -->
      <div class="bubble-header">
        <div class="header-left">
          <span class="tag-pill">{{ tag }}</span>
          <span class="status-indicator">
            <span class="pulse-dot"></span>
            {{ statusText }}
          </span>
        </div>
        <button
          type="button"
          class="bubble-btn-icon btn-close"
          title="关闭气泡"
          aria-label="关闭气泡"
          @click.stop="$emit('close')"
        >
          ✕
        </button>
      </div>

      <!-- 气泡主要内容 -->
      <div class="bubble-content">
        <p class="bubble-text">{{ text }}</p>
      </div>

      <!-- 底部快捷工具栏 -->
      <div class="bubble-actions">
        <button
          type="button"
          class="action-pill"
          title="抽取新运势/换一句"
          @click.stop="$emit('poke')"
        >
          <span class="action-icon">🎲</span>
          <span class="action-label">换一句</span>
        </button>

        <button
          type="button"
          class="action-pill"
          title="一键飞升回顶部"
          @click.stop="$emit('launch')"
        >
          <span class="action-icon">🚀</span>
          <span class="action-label">回顶部</span>
        </button>

        <button
          type="button"
          class="action-pill"
          :class="{ 'is-muted': !isSoundOn }"
          :title="isSoundOn ? '音效已开启 (点击静音)' : '音效已静音 (点击开启)'"
          @click.stop="$emit('toggle-sound')"
        >
          <span class="action-icon">{{ isSoundOn ? '🔔' : '🔕' }}</span>
        </button>

        <button
          v-if="hasCustomPosition"
          type="button"
          class="action-pill"
          title="复位到角落"
          @click.stop="$emit('reset-pos')"
        >
          <span class="action-icon">📍</span>
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.cat-speech-bubble {
  position: absolute;
  bottom: calc(100% + 14px);
  right: 0;
  width: clamp(230px, 32vw, 290px);
  background: var(--paper-warm, #fffdf8);
  border: 1px solid var(--border, #e6ded3);
  border-radius: var(--radius-md, 8px);
  box-shadow: 0 10px 28px rgba(35, 25, 15, 0.16), 0 2px 6px rgba(0, 0, 0, 0.05);
  padding: 0.75rem 0.85rem;
  z-index: 1200;
  pointer-events: auto;
  transform-origin: bottom right;
  backdrop-filter: blur(8px);
}

/* 气泡尖角 */
.bubble-tail {
  position: absolute;
  bottom: -7px;
  right: 36px;
  width: 12px;
  height: 12px;
  background: var(--paper-warm, #fffdf8);
  border-right: 1px solid var(--border, #e6ded3);
  border-bottom: 1px solid var(--border, #e6ded3);
  transform: rotate(45deg);
}

/* 头部 */
.bubble-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.45rem;
  padding-bottom: 0.35rem;
  border-bottom: 1px dashed var(--border, #eee5d8);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.tag-pill {
  font-family: var(--f-mono, monospace);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 0.12rem 0.38rem;
  background: var(--accent, #8b2500);
  color: #ffffff;
  border-radius: 3px;
}

.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 0.28rem;
  font-size: 0.65rem;
  color: var(--muted, #7c7267);
}

.pulse-dot {
  width: 5px;
  height: 5px;
  background: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.25);
  animation: pulseGreen 1.8s infinite;
}

@keyframes pulseGreen {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.7; }
}

.bubble-btn-icon {
  border: 0;
  background: transparent;
  color: var(--muted, #7c7267);
  font-size: 0.72rem;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 3px;
  transition: all 0.15s ease;
}

.bubble-btn-icon:hover {
  background: var(--border, #eee5d8);
  color: var(--ink, #1c1710);
}

/* 正文 */
.bubble-content {
  margin: 0.2rem 0 0.5rem;
}

.bubble-text {
  font-family: var(--f-sans, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
  font-size: 0.8rem;
  line-height: 1.48;
  color: var(--ink, #1c1710);
  margin: 0;
  letter-spacing: 0.01em;
}

/* 底部操作 */
.bubble-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.action-pill {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  border: 1px solid var(--border, #e6ded3);
  background: rgba(255, 255, 255, 0.7);
  padding: 0.2rem 0.45rem;
  border-radius: var(--radius-xs, 4px);
  font-size: 0.65rem;
  color: var(--ink, #1c1710);
  cursor: pointer;
  transition: all 0.18s ease;
}

.action-pill:hover {
  background: var(--ink, #1c1710);
  color: #fffdf8;
  border-color: var(--ink, #1c1710);
  transform: translateY(-1px);
}

.action-pill.is-muted {
  opacity: 0.7;
}

/* 进出过渡动画 */
.bubble-pop-enter-active {
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.bubble-pop-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 1, 1);
}

.bubble-pop-enter-from,
.bubble-pop-leave-to {
  opacity: 0;
  transform: translate3d(0, 12px, 0) scale(0.85);
}

@media (max-width: 640px) {
  .cat-speech-bubble {
    right: -10px;
    width: 220px;
    padding: 0.65rem 0.75rem;
  }
}
</style>
