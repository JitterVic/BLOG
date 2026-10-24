<script setup>
// 首页（DESIGN.md §5.1）：读者进来的第一件事是读到最新的东西。
// 不放横幅：导语之后直接是最新一篇，其后是一份正常滚动的目录。
// 页面正常滚动，不劫持任何输入。

import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import HomeHotLedger from "../components/home/HomeHotLedger.vue";
import PostRow from "../components/PostRow.vue";
import { readTimeLabel } from "../composables/useFormat";
import { useSite } from "../composables/useSite";
import { useTitleMorph } from "../composables/useTitleMorph";
import { getPosts } from "../services/api";
import { useMediaQuery } from "../composables/useMediaQuery";

const LATEST_FETCH_LIMIT = 9; // 最新一篇 + 最近更新 8 篇
const HOT_FETCH_LIMIT = 5;

const { site, ensureSite } = useSite();
const { handleOpen } = useTitleMorph();

const latestPosts = ref([]);
const hotPosts = ref([]);
const postsTotal = ref(0);
const postsError = ref("");
const postsLoading = ref(false);
let postsController = null;
let postsRequestSequence = 0;

const feature = computed(() => latestPosts.value[0] || null);
const recentPosts = computed(() => latestPosts.value.slice(1, LATEST_FETCH_LIMIT));

// 封面两栏版式只在 ≥900px 且确有封面时成立（§5.1）
const wideViewport = useMediaQuery("(min-width: 900px)");
const featureHasCover = computed(() =>
  Boolean(feature.value?.cover_image) && wideViewport.value,
);

const featureTime = computed(() => readTimeLabel(feature.value?.read_time));

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
    latestPosts.value = latestList?.items || [];
    hotPosts.value = hotList?.items || [];
    postsTotal.value = latestList?.total || latestPosts.value.length;
  } catch (err) {
    if (requestId !== postsRequestSequence || err?.code === "REQUEST_ABORTED") return;
    postsError.value = err?.code === "REQUEST_TIMEOUT"
      ? "加载超时。检查网络后重试。"
      : "文章没能加载出来。检查网络后重试。";
  } finally {
    if (requestId === postsRequestSequence) postsLoading.value = false;
  }
}

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // 导语有稳定兜底（字段为空则不渲染），站点元数据缺失不阻塞版面。
  }
  await loadHomePosts();
});

onBeforeUnmount(() => postsController?.abort());
</script>

<template>
  <div class="home-view">
    <p v-if="site?.headline" class="home-intro">{{ site.headline }}</p>

    <AsyncState
      v-if="postsError"
      :error="postsError"
      empty-message="请检查网络后重试。"
      @retry="loadHomePosts"
    />
    <AsyncState
      v-else-if="postsLoading && !latestPosts.length"
      loading
      variant="feature"
      loading-message="正在加载…"
    />

    <template v-else>
      <!-- 最新一篇：标题是页面 h1，也是标题共享转场的出发点 -->
      <section v-if="feature" class="feature" :class="{ 'feature--cover': featureHasCover }">
        <div class="feature__body">
          <h1 class="feature__title">
            <RouterLink
              class="feature__link"
              :to="{ name: 'post', params: { slug: feature.slug } }"
              @click="handleOpen($event, { name: 'post', params: { slug: feature.slug } })"
            >{{ feature.title }}</RouterLink>
          </h1>
          <p v-if="feature.excerpt" class="feature__excerpt">{{ feature.excerpt }}</p>
          <p class="feature__meta">
            <RouterLink
              v-if="feature.category"
              class="feature__meta-link"
              :to="{ name: 'posts', query: { cat: feature.category } }"
            >{{ feature.category }}</RouterLink>
            <time :datetime="feature.published_at">{{ feature.published_at }}</time>
            <span>{{ featureTime }}</span>
          </p>
        </div>
        <RouterLink
          v-if="featureHasCover"
          class="feature__cover"
          :to="{ name: 'post', params: { slug: feature.slug } }"
          tabindex="-1"
          aria-hidden="true"
          @click="handleOpen($event, { name: 'post', params: { slug: feature.slug } })"
        >
          <img :src="feature.cover_image" :alt="feature.title" decoding="async">
        </RouterLink>
        <!-- <900px：封面整宽排在元信息之后 -->
        <RouterLink
          v-else-if="feature.cover_image"
          class="feature__cover feature__cover--stacked"
          :to="{ name: 'post', params: { slug: feature.slug } }"
          tabindex="-1"
          aria-hidden="true"
          @click="handleOpen($event, { name: 'post', params: { slug: feature.slug } })"
        >
          <img :src="feature.cover_image" :alt="feature.title" decoding="async">
        </RouterLink>
      </section>

      <!-- 最近更新 -->
      <section class="home-section" aria-label="最近更新">
        <header class="section-head">
          <h2>最近更新</h2>
          <RouterLink class="text-link" :to="{ name: 'posts' }">全部 {{ postsTotal }} 篇文章</RouterLink>
        </header>
        <div v-if="recentPosts.length">
          <PostRow
            v-for="post in recentPosts"
            :key="post.slug"
            :post="post"
            date-format="full"
          />
        </div>
        <p v-else class="home-section__empty">还没有文章。</p>
      </section>

      <!-- 读得最多 -->
      <section class="home-section" aria-label="读得最多">
        <header class="section-head">
          <h2>读得最多</h2>
        </header>
        <HomeHotLedger :posts="hotPosts" />
      </section>
    </template>
  </div>
</template>
