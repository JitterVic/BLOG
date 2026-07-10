<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { usePosts } from "../composables/usePosts";
import { useSite } from "../composables/useSite";

const route = useRoute();
const router = useRouter();
const { site, ensureSite, error: siteError } = useSite();

const {
  posts,
  error: postsError,
  loading,
  loadPosts,
} = usePosts({ errorMessage: "标签页加载失败，请稍后再试。" });
const selectedTag = ref("全部");

const tags = computed(() => ["全部", ...(site.value?.tags || [])]);
const visiblePosts = computed(() => {
  if (selectedTag.value === "全部") {
    return posts.value;
  }

  return posts.value.filter((post) => post.tags.includes(selectedTag.value));
});

function selectTag(tag) {
  selectedTag.value = tag;
  router.replace({ query: tag === "全部" ? {} : { tag } });
}

function displayDate(value) {
  return value || "未设置日期";
}

watch(
  () => route.query.tag,
  (tag) => {
    selectedTag.value = typeof tag === "string" && tag ? tag : "全部";
  },
  { immediate: true },
);

onMounted(async () => {
  loading.value = true;
  postsError.value = "";

  try {
    await ensureSite();
    await loadPosts();
  } catch (err) {
    postsError.value = "标签页加载失败，请稍后再试。";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="content-view print-subpage print-tags-page">
    <section class="print-page print-section">
      <div class="sec-hd rv vis">
        <span class="sec-hd__n">01</span>
        <h1 class="sec-hd__t">标签 Tags</h1>
        <div class="sec-hd__line"></div>
      </div>

      <div class="print-subpage__meta">
        <span>{{ tags.length - 1 }} 个标签</span>
        <span>{{ visiblePosts.length }} 篇当前筛选</span>
      </div>

      <div class="tag-filter-row print-tag-cloud" role="list" aria-label="标签筛选">
        <button
          v-for="tag in tags"
          :key="tag"
          type="button"
          class="tag-filter-button tag"
          :class="{ active: selectedTag === tag, 'tag--hot': selectedTag === tag }"
          @click="selectTag(tag)"
        >
          {{ tag }}
        </button>
      </div>

      <p v-if="siteError" class="feedback print-feedback">{{ siteError }}</p>
      <p v-else-if="postsError" class="feedback print-feedback">{{ postsError }}</p>
      <p v-else-if="loading" class="feedback print-feedback">标签文章正在加载中……</p>
      <p v-else-if="!visiblePosts.length" class="feedback print-feedback">当前标签下暂无已发布文章。</p>

      <div v-else class="g2e print-tag-results">
        <RouterLink
          v-for="post in visiblePosts"
          :key="post.slug"
          :to="`/posts/${post.slug}`"
          class="art print-article-strip"
        >
          <div class="art__cat">{{ post.category || "Article" }}</div>
          <h2 class="art__t art__t--lg">{{ post.title }}</h2>
          <p class="art__p">{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
          <div class="art__meta">
            <span>{{ displayDate(post.published_at) }}</span>
            <span>{{ post.read_time }}</span>
          </div>
        </RouterLink>
      </div>

      <span class="pg pg--r">— Tags —</span>
    </section>
  </div>
</template>
