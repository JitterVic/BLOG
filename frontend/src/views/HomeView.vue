<script setup>
// 首页（DESIGN.md §5.1）：品牌封面（手写「知至而后意诚」）之后直接是目录——
// 主卷「最近更新」最新一篇领衔（无独立大块），右辅栏「近笺 + 读得最多」。
// 页面正常滚动，不劫持任何输入。

import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import BrandCover from "../components/home/BrandCover.vue";
import HomeHotLedger from "../components/home/HomeHotLedger.vue";
import PostRow from "../components/PostRow.vue";
import { useSite } from "../composables/useSite";
import { useTitleMorph } from "../composables/useTitleMorph";
import { getNotes, getPosts } from "../services/api";

const LATEST_FETCH_LIMIT = 8; // 最近更新 8 篇（含最新一篇）
const HOT_FETCH_LIMIT = 5;
const NOTES_FETCH_LIMIT = 4;

const { site, ensureSite } = useSite();
const { handleOpen } = useTitleMorph();

const latestPosts = ref([]);
const hotPosts = ref([]);
const recentNotes = ref([]);
const postsTotal = ref(0);
const postsError = ref("");
const postsLoading = ref(false);
let postsController = null;
let postsRequestSequence = 0;

async function loadHomePosts() {
  const requestId = ++postsRequestSequence;
  postsController?.abort();
  postsController = new AbortController();
  postsLoading.value = true;
  postsError.value = "";

  try {
    const [latestList, hotList, notesList] = await Promise.all([
      getPosts({ sort: "latest", limit: LATEST_FETCH_LIMIT, signal: postsController.signal }),
      getPosts({ sort: "hot", limit: HOT_FETCH_LIMIT, signal: postsController.signal }),
      getNotes({ limit: NOTES_FETCH_LIMIT, signal: postsController.signal }),
    ]);
    if (requestId !== postsRequestSequence) return;
    latestPosts.value = latestList?.items || [];
    hotPosts.value = hotList?.items || [];
    recentNotes.value = notesList?.items || [];
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
    <!-- 品牌封面：每次进入首页手写一遍「知至而后意诚」（§5.1、§7） -->
    <BrandCover />
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
      variant="rows"
      loading-message="正在加载…"
    />

    <template v-else>
      <!-- 三栏书案：主卷「最近更新」最新一篇领衔，右栏「近笺 + 读得最多」 -->
      <div class="page-grid">
        <section class="page-grid__main home-primary" aria-label="最近更新">
          <header class="section-head">
            <h1>最近更新</h1>
            <RouterLink class="text-link" :to="{ name: 'posts' }">全部 {{ postsTotal }} 篇文章</RouterLink>
          </header>
          <div v-if="latestPosts.length">
            <PostRow
              v-for="post in latestPosts"
              :key="post.slug"
              :post="post"
              date-format="full"
            />
          </div>
          <p v-else class="home-section__empty">还没有文章。</p>
        </section>

        <aside class="page-grid__side home-side" aria-label="余笺与热门">
          <!-- 近笺：像笔记本边上的手记，不与文章列表争夺主层级 -->
          <section class="side-block home-side__notes" aria-label="近笺">
            <header class="side-block__head">
              <h2 class="side-block__title">近笺</h2>
              <RouterLink class="side-block__sub text-link" :to="{ name: 'notes' }">全部余笺</RouterLink>
            </header>
            <div v-if="recentNotes.length">
              <article v-for="note in recentNotes" :key="note.slug" class="home-note-row">
                <p class="home-note-row__meta">
                  <time :datetime="note.published_at">{{ note.published_at }}</time>
                  <span v-if="note.type_label">{{ note.type_label }}</span>
                </p>
                <h3 class="home-note-row__title">
                  <RouterLink
                    class="home-note-row__link"
                    :to="{ name: 'note', params: { slug: note.slug } }"
                    @click="handleOpen($event, { name: 'note', params: { slug: note.slug } })"
                  >{{ note.title }}</RouterLink>
                </h3>
                <p v-if="note.excerpt" class="home-note-row__excerpt">{{ note.excerpt }}</p>
              </article>
            </div>
            <p v-else class="home-section__empty">还没有余笺。</p>
          </section>

          <!-- 读得最多：紧凑行，名次 + 标题 + 阅读数 -->
          <section class="side-block home-hot-strip" aria-label="读得最多">
            <header class="side-block__head">
              <h2 class="side-block__title">读得最多</h2>
              <span class="side-block__sub">前 5 篇</span>
            </header>
            <HomeHotLedger :posts="hotPosts.slice(0, 5)" />
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>
