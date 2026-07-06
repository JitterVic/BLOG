<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { useSite } from "../composables/useSite";
import { getPosts } from "../services/api";

const route = useRoute();
const router = useRouter();
const { site, ensureSite, error: siteError } = useSite();

const posts = ref([]);
const postsError = ref("");
const loading = ref(false);
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
    posts.value = await getPosts();
  } catch (err) {
    postsError.value = "标签页加载失败，请稍后再试。";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="content-view">
    <section class="simple-section">
      <div class="section-head">
        <div>
          <p class="section-label">Tags</p>
          <h2>标签</h2>
        </div>
        <span class="muted-count">{{ tags.length - 1 }} 个标签</span>
      </div>

      <div class="tag-filter-row">
        <button
          v-for="tag in tags"
          :key="tag"
          type="button"
          class="tag-filter-button"
          :class="{ active: selectedTag === tag }"
          @click="selectTag(tag)"
        >
          {{ tag }}
        </button>
      </div>

      <p v-if="siteError" class="feedback">{{ siteError }}</p>
      <p v-else-if="postsError" class="feedback">{{ postsError }}</p>
      <p v-else-if="loading" class="feedback">标签文章正在加载中……</p>
      <p v-else-if="!visiblePosts.length" class="feedback">当前标签下暂无已发布文章。</p>

      <div v-else class="article-list">
        <RouterLink
          v-for="post in visiblePosts"
          :key="post.slug"
          :to="`/posts/${post.slug}`"
          class="article-item"
        >
          <div class="article-meta">
            <span>{{ post.published_at || "未设置日期" }}</span>
            <span>{{ post.read_time }}</span>
          </div>
          <h3>{{ post.title }}</h3>
          <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
        </RouterLink>
      </div>
    </section>
  </div>
</template>
