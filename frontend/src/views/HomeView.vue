<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { useSite } from "../composables/useSite";
import { getPosts } from "../services/api";

const HOME_PANELS = ["cover", "latest", "hot"];
const FLIP_LOCK_MS = 820;

const { site, ensureSite, error: siteError } = useSite();
const posts = ref([]);
const hotPosts = ref([]);
const postsError = ref("");
const postsLoading = ref(false);
const activeHomePanel = ref("cover");
const isHomeFlipping = ref(false);

let homeFlipTimer = 0;

const latestPosts = computed(() => posts.value.slice(0, 5));
const leadPost = computed(() => latestPosts.value[0] || null);
const secondaryPosts = computed(() => latestPosts.value.slice(1));

function formatClicks(count = 0) {
  return `${count} 次阅读`;
}

function finishHomeFlip() {
  isHomeFlipping.value = false;
  if (homeFlipTimer) {
    window.clearTimeout(homeFlipTimer);
    homeFlipTimer = 0;
  }
}

function showHomePanel(panel) {
  if (panel === activeHomePanel.value || isHomeFlipping.value) {
    return false;
  }

  isHomeFlipping.value = true;
  activeHomePanel.value = panel;

  if (homeFlipTimer) {
    window.clearTimeout(homeFlipTimer);
  }
  homeFlipTimer = window.setTimeout(finishHomeFlip, FLIP_LOCK_MS);
  return true;
}

function moveHomePanel(step) {
  const currentIndex = HOME_PANELS.indexOf(activeHomePanel.value);
  const nextIndex = Math.min(Math.max(currentIndex + step, 0), HOME_PANELS.length - 1);
  return showHomePanel(HOME_PANELS[nextIndex]);
}

function handleHomeWheel(event) {
  const intent = Math.abs(event.deltaY);
  if (intent <= 18) {
    return;
  }

  if (isHomeFlipping.value) {
    event.preventDefault();
    return;
  }

  const moved = moveHomePanel(event.deltaY > 0 ? 1 : -1);
  if (moved) {
    event.preventDefault();
  }
}

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // The UI already renders a friendlier message via siteError.
  }

  postsLoading.value = true;
  postsError.value = "";
  try {
    const [latestList, hotList] = await Promise.all([
      getPosts({ sort: "latest" }),
      getPosts({ sort: "hot", limit: 5 }),
    ]);
    posts.value = latestList;
    hotPosts.value = hotList;
  } catch (err) {
    postsError.value = "文章入口暂时加载失败，请稍后再试。";
  } finally {
    postsLoading.value = false;
  }
});

onBeforeUnmount(() => {
  if (homeFlipTimer) {
    window.clearTimeout(homeFlipTimer);
  }
});
</script>

<template>
  <div class="home-view personal-home spacious-home calendar-home-view">
    <div class="calendar-stage home-calendar-stage" @wheel="handleHomeWheel">
      <Transition name="calendar-flip" mode="out-in" @after-enter="finishHomeFlip">
        <section
          v-if="activeHomePanel === 'cover'"
          key="home-cover"
          class="spacious-cover calendar-page journal-cover-only"
          aria-label="首页封面"
        >
          <span class="calendar-watermark" aria-hidden="true"></span>
          <h1 class="journal-title">ZHI ZHI JOURNAL</h1>

          <p v-if="siteError" class="feedback cover-feedback">{{ siteError }}</p>

          <div class="spacious-cover-actions calendar-actions" aria-label="首页入口">
            <button
              type="button"
              class="cover-button primary-link calendar-control"
              @click="showHomePanel('latest')"
            >
              阅读最近文章
            </button>
            <button
              type="button"
              class="cover-button calendar-control"
              @click="showHomePanel('hot')"
            >
              查看热点文章
            </button>
          </div>
        </section>

        <section
          v-else-if="activeHomePanel === 'latest'"
          id="latest-posts"
          key="home-latest"
          class="simple-section latest-spacious-section calendar-page home-article-panel latest-calendar-panel"
          aria-label="最近文章"
        >
          <span class="calendar-watermark" aria-hidden="true"></span>
          <div class="section-head spacious-section-head calendar-section-head">
            <div>
              <p class="section-label">Latest writing</p>
              <h2>最近文章</h2>
            </div>
            <div class="calendar-panel-actions">
              <button type="button" class="calendar-back-button" @click="showHomePanel('cover')">
                返回封面
              </button>
              <button type="button" class="calendar-back-button" @click="showHomePanel('hot')">
                热点文章
              </button>
              <RouterLink to="/posts" class="text-link">全部文章 →</RouterLink>
            </div>
          </div>

          <p v-if="postsError" class="feedback">{{ postsError }}</p>
          <p v-else-if="postsLoading" class="feedback">文章正在装订中……</p>
          <p v-else-if="!latestPosts.length" class="feedback">还没有已发布文章，先去后台发布第一篇。</p>

          <div v-else class="latest-spacious-layout">
            <RouterLink
              v-if="leadPost"
              :to="`/posts/${leadPost.slug}`"
              class="article-item latest-lead-card"
            >
              <div class="article-meta">
                <span>{{ leadPost.published_at }}</span>
                <span>{{ leadPost.read_time }}</span>
                <span>{{ formatClicks(leadPost.click_count) }}</span>
              </div>
              <h3>{{ leadPost.title }}</h3>
              <p>{{ leadPost.excerpt || "这篇文章暂时还没有摘要。" }}</p>
              <div class="article-card-foot">
                <span>{{ leadPost.category || "Note" }}</span>
                <span>阅读全文 →</span>
              </div>
            </RouterLink>

            <div class="latest-spacious-list" aria-label="更多最近文章">
              <RouterLink
                v-for="post in secondaryPosts"
                :key="post.slug"
                :to="`/posts/${post.slug}`"
                class="latest-row-link"
              >
                <span>{{ post.published_at }}</span>
                <strong>{{ post.title }}</strong>
                <small>{{ formatClicks(post.click_count) }} · {{ post.read_time }}</small>
              </RouterLink>
            </div>
          </div>
        </section>

        <section
          v-else
          id="hot-posts"
          key="home-hot"
          class="simple-section hot-spacious-section calendar-page home-article-panel hot-calendar-panel"
          aria-label="热点文章"
        >
          <span class="calendar-watermark" aria-hidden="true"></span>
          <div class="section-head spacious-section-head calendar-section-head">
            <div>
              <p class="section-label">Most opened</p>
              <h2>热点文章</h2>
            </div>
            <div class="calendar-panel-actions">
              <button type="button" class="calendar-back-button dark" @click="showHomePanel('cover')">
                返回封面
              </button>
              <button type="button" class="calendar-back-button dark" @click="showHomePanel('latest')">
                最近文章
              </button>
              <span class="hot-sort-note">按点击数排序</span>
            </div>
          </div>

          <p v-if="postsLoading" class="feedback">热点文章正在整理中……</p>
          <p v-else-if="!hotPosts.length" class="feedback">还没有阅读数据，打开文章后这里会自动更新。</p>

          <div v-else class="hot-spacious-grid">
            <RouterLink
              v-for="(post, index) in hotPosts"
              :key="post.slug"
              :to="`/posts/${post.slug}`"
              class="hot-spacious-card"
            >
              <span class="hot-rank">{{ String(index + 1).padStart(2, "0") }}</span>
              <strong>{{ post.title }}</strong>
              <small>{{ formatClicks(post.click_count) }} · {{ post.published_at }}</small>
            </RouterLink>
          </div>
        </section>
      </Transition>
    </div>
  </div>
</template>

