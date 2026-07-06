<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useSite } from "../composables/useSite";

const ABOUT_PANELS = ["cover", "story", "contact"];
const FLIP_LOCK_MS = 820;

const { site, ensureSite, error } = useSite();
const activeAboutPanel = ref("cover");
const isAboutFlipping = ref(false);
let aboutFlipTimer = 0;

const introParagraphs = computed(() => {
  const paragraphs = site.value?.about_intro || [];
  if (paragraphs.length) return paragraphs.slice(0, 2);
  return [
    "至知是一个把学习过程公开整理出来的个人空间。这里不追求堆满信息，而是把项目实践、技术复盘和阅读笔记沉淀成以后还能复用的路径。",
    "我更关心一件事：把做过的东西讲清楚。每篇文章都尽量留下背景、判断、取舍和可执行的方法，而不是只保存结果。",
  ];
});
const contactLinks = computed(() => site.value?.social_links || []);

function finishAboutFlip() {
  isAboutFlipping.value = false;
  if (aboutFlipTimer) {
    window.clearTimeout(aboutFlipTimer);
    aboutFlipTimer = 0;
  }
}

function showAboutPanel(panel) {
  if (panel === activeAboutPanel.value || isAboutFlipping.value) {
    return false;
  }

  isAboutFlipping.value = true;
  activeAboutPanel.value = panel;

  if (aboutFlipTimer) {
    window.clearTimeout(aboutFlipTimer);
  }
  aboutFlipTimer = window.setTimeout(finishAboutFlip, FLIP_LOCK_MS);
  return true;
}

function moveAboutPanel(step) {
  const currentIndex = ABOUT_PANELS.indexOf(activeAboutPanel.value);
  const nextIndex = Math.min(Math.max(currentIndex + step, 0), ABOUT_PANELS.length - 1);
  return showAboutPanel(ABOUT_PANELS[nextIndex]);
}

function handleAboutWheel(event) {
  const intent = Math.abs(event.deltaY);
  if (intent <= 18) {
    return;
  }

  if (isAboutFlipping.value) {
    event.preventDefault();
    return;
  }

  const moved = moveAboutPanel(event.deltaY > 0 ? 1 : -1);
  if (moved) {
    event.preventDefault();
  }
}

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // The UI already renders a friendlier message via error.
  }
});

onBeforeUnmount(() => {
  if (aboutFlipTimer) {
    window.clearTimeout(aboutFlipTimer);
  }
});
</script>

<template>
  <div class="content-view about-view minimal-about-view about-calendar-view">
    <div class="calendar-stage about-calendar-stage" @wheel="handleAboutWheel">
      <Transition name="calendar-flip" mode="out-in" @after-enter="finishAboutFlip">
        <section
          v-if="activeAboutPanel === 'cover'"
          key="about-cover"
          class="minimal-about-hero calendar-page about-cover-page"
          aria-label="关于至知"
        >
          <span class="calendar-watermark" aria-hidden="true"></span>
          <h1>About Zhizhi</h1>
          <div class="spacious-cover-actions calendar-actions" aria-label="关于页入口">
            <button
              type="button"
              class="cover-button primary-link calendar-control"
              @click="showAboutPanel('story')"
            >
              阅读自述
            </button>
            <button
              type="button"
              class="cover-button calendar-control"
              @click="showAboutPanel('contact')"
            >
              联系方式
            </button>
          </div>
        </section>

        <section
          v-else-if="activeAboutPanel === 'story'"
          key="about-story"
          class="minimal-about-card calendar-page about-story-page"
          aria-label="自述"
        >
          <span class="calendar-watermark" aria-hidden="true"></span>
          <div class="minimal-about-mark">至知</div>
          <div class="minimal-about-copy">
            <div class="calendar-section-head inline">
              <div>
                <p class="section-label">Self note</p>
                <h2>{{ site?.name || "至知" }}记录什么</h2>
              </div>
              <div class="calendar-panel-actions compact">
                <button type="button" class="calendar-back-button" @click="showAboutPanel('cover')">
                  返回封面
                </button>
                <button type="button" class="calendar-back-button" @click="showAboutPanel('contact')">
                  联系方式
                </button>
              </div>
            </div>
            <p v-for="paragraph in introParagraphs" :key="paragraph">{{ paragraph }}</p>
          </div>
        </section>

        <section
          v-else
          key="about-contact"
          class="minimal-contact-strip calendar-page about-contact-page"
          aria-label="交流入口"
        >
          <span class="calendar-watermark" aria-hidden="true"></span>
          <div>
            <p class="section-label">Contact</p>
            <h2>如果你想交流</h2>
            <div class="calendar-panel-actions compact about-contact-actions">
              <button type="button" class="calendar-back-button" @click="showAboutPanel('cover')">
                返回封面
              </button>
              <button type="button" class="calendar-back-button" @click="showAboutPanel('story')">
                阅读自述
              </button>
            </div>
          </div>
          <div v-if="contactLinks.length" class="minimal-contact-links">
            <a
              v-for="item in contactLinks"
              :key="item.label"
              :href="item.url"
              target="_blank"
              rel="noreferrer"
              class="social-link"
            >
              {{ item.label }} · {{ item.value }}
            </a>
          </div>
          <p v-else class="feedback">暂未配置联系方式。</p>
        </section>
      </Transition>
    </div>

    <section v-if="error" class="simple-section about-error-section">
      <p class="feedback">{{ error }}</p>
    </section>
  </div>
</template>

