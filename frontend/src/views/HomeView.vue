<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import HomeCover from "../components/home/HomeCover.vue";
import HomeFeature from "../components/home/HomeFeature.vue";
import HomeHotLedger from "../components/home/HomeHotLedger.vue";
import HomeLatestIndex from "../components/home/HomeLatestIndex.vue";
import HomePageRail from "../components/home/HomePageRail.vue";
import { usePageFlip } from "../composables/usePageFlip";
import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";
import { getPosts } from "../services/api";

const HOME_POST_LIMIT = 5;

const { ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });
const { isFlipActive, trackStyle } = usePageFlip();
const latestPosts = ref([]);
const hotPosts = ref([]);
const postsError = ref("");
const postsLoading = ref(false);
let postsController = null;
let postsRequestSequence = 0;

const leadPost = computed(() => latestPosts.value[0] || null);
const secondaryPosts = computed(() => latestPosts.value.slice(1));

watch([latestPosts, hotPosts, postsLoading], () => {
  refreshReveal();
});

async function loadHomePosts() {
  const requestId = ++postsRequestSequence;
  postsController?.abort();
  postsController = new AbortController();
  postsLoading.value = true;
  postsError.value = "";

  try {
    const [latestList, hotList] = await Promise.all([
      getPosts({ sort: "latest", limit: HOME_POST_LIMIT, signal: postsController.signal }),
      getPosts({ sort: "hot", limit: HOME_POST_LIMIT, signal: postsController.signal }),
    ]);
    if (requestId !== postsRequestSequence) return;
    latestPosts.value = Array.isArray(latestList) ? latestList : (latestList?.items || []);
    hotPosts.value = Array.isArray(hotList) ? hotList : (hotList?.items || []);
  } catch (err) {
    if (requestId !== postsRequestSequence || err?.code === "REQUEST_ABORTED") return;
    postsError.value = err?.code === "REQUEST_TIMEOUT"
      ? "文章加载超时，请稍后再试。"
      : "文章暂时无法加载，请稍后再试。";
  } finally {
    if (requestId === postsRequestSequence) {
      postsLoading.value = false;
      refreshReveal();
    }
  }
}

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // The cover keeps a stable fallback title when site metadata is unavailable.
  }
  await loadHomePosts();
});

onBeforeUnmount(() => postsController?.abort());
</script>

<template>
  <div class="home-view print-home focused-home" :class="{ 'flip-mode': isFlipActive }">
    <HomePageRail />
    <div class="flip-track" :style="trackStyle">
    <HomeCover />

    <section id="latest" class="print-page print-section home-latest-section" aria-label="最近更新">
      <div class="sec-hd rv rv--left">
        <span class="sec-hd__n">02</span>
        <h2 class="sec-hd__t">最近更新 Latest</h2>
        <div class="sec-hd__line"></div>
      </div>

      <AsyncState
        v-if="postsError"
        :error="postsError"
        empty-message="请检查网络连接后重试。"
        @retry="loadHomePosts"
      />

      <div v-else-if="postsLoading" class="home-skeleton-stack" aria-busy="true" aria-label="文章装订中">
        <div class="home-skeleton-feature">
          <div class="sk-block sk-block--tall"></div>
          <div class="sk-copy">
            <div class="sk-line sk-line--sm"></div>
            <div class="sk-line sk-line--lg"></div>
            <div class="sk-line"></div>
            <div class="sk-line sk-line--md"></div>
          </div>
        </div>
        <div v-for="n in 3" :key="n" class="sk-row">
          <div class="sk-line sk-line--xs"></div>
          <div class="sk-line sk-line--md"></div>
          <div class="sk-line"></div>
        </div>
      </div>

      <AsyncState
        v-else-if="!latestPosts.length"
        empty
        empty-title="还没有已发布文章"
        empty-message="等下一期内容整理完成后再来看看。"
      />

      <template v-else>
        <HomeFeature v-if="leadPost" :post="leadPost" />
        <HomeLatestIndex v-if="secondaryPosts.length" :posts="secondaryPosts" />
      </template>

      <div class="home-section-footer rv">
        <RouterLink to="/posts" class="cover-button">浏览全部文章</RouterLink>
      </div>
      <span class="pg pg--l">— 002 —</span>
    </section>

    <section id="hot" class="print-page print-section home-hot-section" aria-label="热点文章">
      <div class="sec-hd rv rv--left">
        <span class="sec-hd__n">03</span>
        <h2 class="sec-hd__t">热点文章 Most Read</h2>
        <div class="sec-hd__line"></div>
      </div>

      <AsyncState
        v-if="postsError"
        :error="postsError"
        empty-message="请检查网络连接后重试。"
        @retry="loadHomePosts"
      />

      <div v-else-if="postsLoading" class="home-hot-ledger home-skeleton-hot" aria-busy="true">
        <div v-for="n in 4" :key="n" class="sk-hot-row">
          <div class="sk-line sk-line--rank"></div>
          <div class="sk-copy">
            <div class="sk-line sk-line--sm"></div>
            <div class="sk-line sk-line--lg"></div>
            <div class="sk-line sk-line--md"></div>
          </div>
        </div>
      </div>

      <AsyncState
        v-else-if="!hotPosts.length"
        empty
        empty-title="还没有阅读数据"
        empty-message="热点文章将在有阅读记录后显示。"
      />

      <HomeHotLedger v-else :posts="hotPosts" />

      <div class="home-section-footer rv">
        <RouterLink to="/posts" class="cover-button primary-link">进入文章目录</RouterLink>
      </div>
      <span class="pg pg--r">— 003 —</span>
    </section>
    </div>
  </div>
</template>
