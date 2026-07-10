<script setup>
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { useSite } from "../composables/useSite";
import { getPosts } from "../services/api";

const HOME_POST_LIMIT = 5;

const { site, ensureSite } = useSite();
const latestPosts = ref([]);
const hotPosts = ref([]);
const postsError = ref("");
const postsLoading = ref(false);

const leadPost = computed(() => latestPosts.value[0] || null);
const secondaryPosts = computed(() => latestPosts.value.slice(1));
const issueMonth = computed(() => new Intl.DateTimeFormat("en-US", {
  month: "long",
  year: "numeric",
}).format(new Date()));

function displayDate(value) {
  return value || "未设置日期";
}

function formatClicks(count = 0) {
  return `${count || 0} 次阅读`;
}

onMounted(async () => {
  try {
    await ensureSite();
  } catch (err) {
    // The cover keeps a stable fallback title when site metadata is unavailable.
  }

  postsLoading.value = true;
  postsError.value = "";

  try {
    const [latestList, hotList] = await Promise.all([
      getPosts({ sort: "latest", limit: HOME_POST_LIMIT }),
      getPosts({ sort: "hot", limit: HOME_POST_LIMIT }),
    ]);
    latestPosts.value = latestList;
    hotPosts.value = hotList;
  } catch (err) {
    postsError.value = "文章暂时无法加载，请稍后再试。";
  } finally {
    postsLoading.value = false;
  }
});
</script>

<template>
  <div class="home-view print-home focused-home">
    <section id="cover" class="print-page print-cover focused-cover" aria-label="首页封面">
      <div class="print-cover__masthead">
        <span>Vol. IX · Digital Edition</span>
        <span>{{ issueMonth }}</span>
      </div>

      <div class="focused-cover__body">
        <h1>
          {{ site?.name || "至知" }}<br>
          <em>Journal</em>
        </h1>
        <div class="print-accent-rule" aria-hidden="true"></div>

        <div class="focused-cover__actions" aria-label="首页文章入口">
          <a href="#latest" class="cover-button primary-link">最近更新</a>
          <a href="#hot" class="cover-button">热点文章</a>
        </div>
      </div>

      <a class="print-scroll-cue" href="#latest">▼ 向下翻阅 Scroll to explore ▼</a>
      <span class="pg pg--r">— 001 —</span>
    </section>

    <section id="latest" class="print-page print-section home-latest-section" aria-label="最近更新">
      <div class="sec-hd rv vis">
        <span class="sec-hd__n">02</span>
        <h2 class="sec-hd__t">最近更新 Latest</h2>
        <div class="sec-hd__line"></div>
      </div>

      <p v-if="postsError" class="feedback print-feedback">{{ postsError }}</p>
      <p v-else-if="postsLoading" class="feedback print-feedback">文章正在装订中……</p>
      <p v-else-if="!latestPosts.length" class="feedback print-feedback">还没有已发布文章。</p>

      <template v-else>
        <div v-if="leadPost" class="g2 home-latest-feature rv vis">
          <RouterLink :to="`/posts/${leadPost.slug}`" class="mimg print-feature-image">
            <div class="print-feature-art">
              <span v-for="tag in leadPost.tags?.slice(0, 3)" :key="tag" class="tag tag--code">{{ tag }}</span>
              <h2>{{ leadPost.title }}</h2>
              <p>{{ leadPost.excerpt || "这篇文章暂时还没有摘要。" }}</p>
            </div>
            <div class="mimg__cap">cover story — {{ displayDate(leadPost.published_at) }}</div>
          </RouterLink>

          <article class="art print-lead-copy">
            <div class="art__cat">Latest Issue</div>
            <h3 class="art__t art__t--xl dc">{{ leadPost.title }}</h3>
            <p class="art__p">{{ leadPost.excerpt || "这篇文章暂时还没有摘要。" }}</p>
            <div class="art__meta">
              <span>{{ leadPost.category || "Article" }}</span>
              <span>{{ leadPost.read_time }}</span>
              <span>{{ displayDate(leadPost.published_at) }}</span>
            </div>
            <RouterLink :to="`/posts/${leadPost.slug}`" class="text-link print-read-more">阅读全文 →</RouterLink>
          </article>
        </div>

        <div v-if="secondaryPosts.length" class="home-latest-index rv vis">
          <RouterLink
            v-for="(post, index) in secondaryPosts"
            :key="post.slug"
            :to="`/posts/${post.slug}`"
            class="home-index-row"
          >
            <span class="home-index-row__number">{{ String(index + 2).padStart(2, "0") }}</span>
            <span class="home-index-row__date">{{ displayDate(post.published_at) }}</span>
            <strong>{{ post.title }}</strong>
            <small>{{ post.category || "Article" }} · {{ post.read_time }}</small>
          </RouterLink>
        </div>
      </template>

      <div class="home-section-footer">
        <RouterLink to="/posts" class="cover-button">浏览全部文章</RouterLink>
      </div>
      <span class="pg pg--l">— 002 —</span>
    </section>

    <section id="hot" class="print-page print-section home-hot-section" aria-label="热点文章">
      <div class="sec-hd rv vis">
        <span class="sec-hd__n">03</span>
        <h2 class="sec-hd__t">热点文章 Most Read</h2>
        <div class="sec-hd__line"></div>
      </div>

      <p v-if="postsError" class="feedback print-feedback">{{ postsError }}</p>
      <p v-else-if="postsLoading" class="feedback print-feedback">阅读排行正在整理中……</p>
      <p v-else-if="!hotPosts.length" class="feedback print-feedback">还没有阅读数据。</p>

      <div v-else class="home-hot-ledger rv vis">
        <RouterLink
          v-for="(post, index) in hotPosts"
          :key="post.slug"
          :to="`/posts/${post.slug}`"
          class="home-hot-row"
        >
          <span class="home-hot-row__rank">{{ String(index + 1).padStart(2, "0") }}</span>
          <div class="home-hot-row__copy">
            <span class="art__cat">{{ post.category || "Most Read" }}</span>
            <h3>{{ post.title }}</h3>
            <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
          </div>
          <div class="home-hot-row__meta">
            <strong>{{ formatClicks(post.click_count) }}</strong>
            <span>{{ displayDate(post.published_at) }}</span>
          </div>
        </RouterLink>
      </div>

      <div class="home-section-footer">
        <RouterLink to="/posts" class="cover-button primary-link">进入文章目录</RouterLink>
      </div>
      <span class="pg pg--r">— 003 —</span>
    </section>
  </div>
</template>
