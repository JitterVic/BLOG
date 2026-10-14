<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import HomeCover from "../components/home/HomeCover.vue";
import HomeFeature from "../components/home/HomeFeature.vue";
import HomeHotLedger from "../components/home/HomeHotLedger.vue";
import HomeLatestRow from "../components/home/HomeLatestRow.vue";
import HomePageRail from "../components/home/HomePageRail.vue";
import { usePageFlip } from "../composables/usePageFlip";
import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";
import { getPosts } from "../services/api";

// 第 2 版：头条 1 篇 + 次要 2 篇，同一套版式、依次缩小一档。
const LATEST_FETCH_LIMIT = 3;
const HOT_FETCH_LIMIT = 5;

const { ensureSite } = useSite();
const { refresh: refreshReveal, replayReveal } = useReveal({ reobserveOnRoute: false });
const { isFlipActive, trackStyle, currentPage } = usePageFlip();
const homeRootRef = ref(null);
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

// 首页整屏翻页：正文不滚动，所以目标版面里的 `.rv` 早已被观察器标成 `.vis`
// （或反过来一直没被揭示），单靠 IntersectionObserver 既不会重播、也可能迟迟不显示
// （实测翻到第 2 版后内容 op=0，要等 4s 兜底才现形）。
// 这里在切版后显式重播「当前版 + 上一版」的入场动效：两个版面都重播，
// 让前进/后退都能看到层次。
watch([currentPage, isFlipActive], async ([page, active], previous) => {
  if (!active) return;
  const previousPage = Array.isArray(previous) ? previous[0] : page;
  if (page === previousPage) return;
  const root = homeRootRef.value;
  if (!root) return;
  const sections = root.querySelectorAll(".flip-track > .print-page");
  await nextTick();
  // 只重播「刚进入的那一版」。早期版本把「当前版 + 上一版」都重播，结果是：
  // ① 切到第 2/3 版时封面在屏幕外空转一遍，之后再切回封面 / 从第 3 版切回封面，
  //    封面早已是 .vis，没有任何重播；
  // ② 两个版面同时起动画，与 850ms 的翻页位移叠加，观感更卡。
  await replayReveal(sections[page]);
});

async function loadHomePosts() {
  const requestId = ++postsRequestSequence;
  postsController?.abort();
  postsController = new AbortController();
  postsLoading.value = true;
  postsError.value = "";

  try {
    const [latestList, hotList] = await Promise.all([
      getPosts({ sort: "latest", limit: LATEST_FETCH_LIMIT, signal: postsController.signal }),
      getPosts({ sort: "hot", limit: HOT_FETCH_LIMIT, signal: postsController.signal }),
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
  <div ref="homeRootRef" class="home-view print-home focused-home" :class="{ 'flip-mode': isFlipActive }">
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
        <!-- 第 2 版：头条用大版式铺满主区，其余 2 篇以同一套版式缩小一档排在下方，
             形成「头版头条 + 次要稿件」的主从关系；更多文章交给第 3 版与文章目录。 -->
        <HomeFeature v-if="leadPost" :post="leadPost" :site-name="site?.name || '至知'" />
        <HomeLatestRow v-if="secondaryPosts.length" :posts="secondaryPosts" />
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
