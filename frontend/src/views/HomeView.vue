<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { useReveal } from "../composables/useReveal";
import { useSite } from "../composables/useSite";
import { getPosts } from "../services/api";

const HOME_POST_LIMIT = 5;

const { site, ensureSite } = useSite();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });
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
const issueNumber = computed(() => {
  const now = new Date();
  return String(now.getMonth() + 1).padStart(2, "0");
});

function displayDate(value) {
  return value || "未设置日期";
}

function formatClicks(count = 0) {
  return `${count || 0} 次阅读`;
}


watch([latestPosts, hotPosts, postsLoading], () => {
  refreshReveal();
});


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
    refreshReveal();
  }
});
</script>

<template>
  <div class="home-view print-home focused-home">
    <section id="cover" class="print-page print-cover focused-cover" aria-label="首页封面">
      <div class="print-cover__masthead rv" data-reveal-delay="0">
        <span>Vol. {{ issueNumber }} · Digital Edition</span>
        <span>{{ issueMonth }}</span>
      </div>

      <div class="focused-cover__body">
        <p class="cover-kicker rv" data-reveal-delay="40">Personal Technical Journal</p>
        <h1 class="rv cover-title" data-reveal-delay="80">
          {{ site?.name || "至知" }}<br>
          <em>Journal</em>
        </h1>
        <div class="print-accent-rule rv" data-reveal-delay="160" aria-hidden="true"></div>
        <p class="print-cover__summary rv" data-reveal-delay="220">
          {{ site?.headline || "以报刊式排版重装技术笔记，让阅读再次拥有翻页的停顿感。" }}
        </p>

        <div class="focused-cover__actions rv" data-reveal-delay="280" aria-label="首页文章入口">
          <a href="#latest" class="cover-button primary-link">最近更新</a>
          <a href="#hot" class="cover-button">热点文章</a>
          <RouterLink to="/posts" class="cover-button ghost-link">全部目录</RouterLink>
        </div>
      </div>

      <a class="print-scroll-cue" href="#latest">
        <span class="print-scroll-cue__icon" aria-hidden="true">↓</span>
        <span>向下翻阅 · Scroll to explore</span>
      </a>
      <span class="pg pg--r">— 001 —</span>
    </section>

    <section id="latest" class="print-page print-section home-latest-section" aria-label="最近更新">
      <div class="sec-hd rv">
        <span class="sec-hd__n">02</span>
        <h2 class="sec-hd__t">最近更新 Latest</h2>
        <div class="sec-hd__line"></div>
      </div>

      <p v-if="postsError" class="feedback print-feedback rv">{{ postsError }}</p>

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

      <p v-else-if="!latestPosts.length" class="feedback print-feedback rv">还没有已发布文章。</p>

      <template v-else>
        <div
          v-if="leadPost"
          class="g2 home-latest-feature"
          data-feature-card="latest"
        >
          <RouterLink
            :to="`/posts/${leadPost.slug}`"
            class="mimg print-feature-image rv"
            data-reveal-delay="40"
          >
            <div class="feature-spotlight" aria-hidden="true"></div>
            <div class="feature-poster-mark" aria-hidden="true">
              <span>NEW</span>
              <strong>01</strong>
            </div>
            <div class="feature-orbit" aria-hidden="true">
              <i></i><i></i><i></i>
            </div>
            <div class="print-feature-art">
              <div class="feature-tags">
                <span
                  v-for="tag in leadPost.tags?.slice(0, 3)"
                  :key="tag"
                  class="tag tag--code"
                >{{ tag }}</span>
              </div>
              <span class="feature-kicker">Editor’s pick · 最新一期</span>
              <h2>{{ leadPost.title }}</h2>
              <p>{{ leadPost.excerpt || "这篇文章暂时还没有摘要。" }}</p>
              <span class="feature-open-hint" aria-hidden="true">打开文章 <b>↗</b></span>
            </div>
            <div class="mimg__cap">cover story — {{ displayDate(leadPost.published_at) }}</div>
          </RouterLink>

          <article class="art print-lead-copy rv" data-reveal-delay="120">
            <div class="print-lead-copy__inner">
              <div class="lead-issue-line">
                <div class="art__cat">Latest Issue</div>
                <span>Vol. {{ issueNumber }}</span>
              </div>
              <h3 class="art__t art__t--xl">{{ leadPost.title }}</h3>
              <p class="art__p">{{ leadPost.excerpt || "这篇文章暂时还没有摘要。" }}</p>
              <div class="art__meta">
                <span>{{ leadPost.category || "Article" }}</span>
                <span>{{ leadPost.read_time }}</span>
                <span>{{ displayDate(leadPost.published_at) }}</span>
              </div>
              <RouterLink :to="`/posts/${leadPost.slug}`" class="text-link print-read-more">
                阅读全文 →
              </RouterLink>
            </div>
          </article>
        </div>

        <div v-if="secondaryPosts.length" class="home-latest-index">
          <RouterLink
            v-for="(post, index) in secondaryPosts"
            :key="post.slug"
            :to="`/posts/${post.slug}`"
            class="home-index-row rv"
            :data-reveal-delay="index * 60"
          >
            <span class="home-index-row__number">{{ String(index + 2).padStart(2, "0") }}</span>
            <span class="home-index-row__date">{{ displayDate(post.published_at) }}</span>
            <strong>{{ post.title }}</strong>
            <small>{{ post.category || "Article" }} · {{ post.read_time }}</small>
          </RouterLink>
        </div>
      </template>

      <div class="home-section-footer rv">
        <RouterLink to="/posts" class="cover-button">浏览全部文章</RouterLink>
      </div>
      <span class="pg pg--l">— 002 —</span>
    </section>

    <section id="hot" class="print-page print-section home-hot-section" aria-label="热点文章">
      <div class="sec-hd rv">
        <span class="sec-hd__n">03</span>
        <h2 class="sec-hd__t">热点文章 Most Read</h2>
        <div class="sec-hd__line"></div>
      </div>

      <p v-if="postsError" class="feedback print-feedback rv">{{ postsError }}</p>

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

      <p v-else-if="!hotPosts.length" class="feedback print-feedback rv">还没有阅读数据。</p>

      <div v-else class="home-hot-ledger">
        <RouterLink
          v-for="(post, index) in hotPosts"
          :key="post.slug"
          :to="`/posts/${post.slug}`"
          class="home-hot-row rv"
          :data-reveal-delay="index * 70"
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

      <div class="home-section-footer rv">
        <RouterLink to="/posts" class="cover-button primary-link">进入文章目录</RouterLink>
      </div>
      <span class="pg pg--r">— 003 —</span>
    </section>
  </div>
</template>
