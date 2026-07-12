<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { usePosts } from "../composables/usePosts";
import { useReveal } from "../composables/useReveal";

const VIEW_OPTIONS = [
  { id: "latest", label: "最新文章", english: "Latest" },
  { id: "archive", label: "归档查找", english: "Archive" },
  { id: "tags", label: "标签筛选", english: "Tags" },
];

const {
  posts,
  error,
  loading,
  loadPosts,
} = usePosts({ errorMessage: "文章目录加载失败，请稍后再试。" });

const route = useRoute();
const { refresh: refreshReveal } = useReveal({ reobserveOnRoute: false });
const activeView = ref("latest");
const searchQuery = ref("");
const selectedTag = ref("全部");

const normalizedQuery = computed(() => searchQuery.value.trim().toLowerCase());
const tags = computed(() => {
  const values = new Set();
  for (const post of posts.value) {
    for (const tag of post.tags || []) values.add(tag);
  }
  return ["全部", ...Array.from(values).sort((a, b) => a.localeCompare(b, "zh-CN"))];
});

const searchMatchedPosts = computed(() => {
  if (!normalizedQuery.value) return posts.value;

  return posts.value.filter((post) => {
    const searchable = [
      post.title,
      post.excerpt,
      ...(post.tags || []),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return searchable.includes(normalizedQuery.value);
  });
});

const visiblePosts = computed(() => {
  if (activeView.value !== "tags" || selectedTag.value === "全部") {
    return searchMatchedPosts.value;
  }

  return searchMatchedPosts.value.filter((post) => post.tags?.includes(selectedTag.value));
});

const groupedPosts = computed(() => {
  const groups = new Map();
  for (const post of visiblePosts.value) {
    const year = (post.published_at || "未归档").slice(0, 4);
    if (!groups.has(year)) groups.set(year, []);
    groups.get(year).push(post);
  }
  return Array.from(groups.entries());
});

const resultLabel = computed(() => {
  if (activeView.value === "tags" && selectedTag.value !== "全部") {
    return `${selectedTag.value} · ${visiblePosts.value.length} 篇`;
  }
  if (normalizedQuery.value) {
    return `搜索结果 · ${visiblePosts.value.length} 篇`;
  }
  return `共 ${visiblePosts.value.length} 篇文章`;
});

function setView(view) {
  activeView.value = view;
  if (view !== "tags") selectedTag.value = "全部";
}

function selectTag(tag) {
  selectedTag.value = tag;
}

function clearSearch() {
  searchQuery.value = "";
}

function clearAllFilters() {
  searchQuery.value = "";
  selectedTag.value = "全部";
}

function displayDate(value) {
  return value || "未设置日期";
}

function shortDate(value) {
  if (!value) return "--.--";
  const [, month, day] = value.split("-");
  return month && day ? `${month}-${day}` : value;
}

function applyRouteTag() {
  const tag = typeof route.query.tag === "string" ? route.query.tag.trim() : "";
  if (tag) {
    activeView.value = "tags";
    selectedTag.value = tag;
  }
}

watch([visiblePosts, activeView, loading], () => {
  refreshReveal();
});

watch(
  () => route.query.tag,
  () => {
    applyRouteTag();
  },
);

onMounted(async () => {
  applyRouteTag();
  await loadPosts({ sort: "latest" });
  refreshReveal();
});
</script>

<template>
  <div class="content-view print-subpage unified-posts-page">
    <section class="print-page print-section">
      <p class="posts-chapter-label rv">Catalog of Issues</p>
      <div class="sec-hd rv">
        <span class="sec-hd__n">02</span>
        <h1 class="sec-hd__t">文章 Articles</h1>
        <div class="sec-hd__line"></div>
      </div>

      <div class="article-toolbox rv">
        <div class="article-view-switch" role="tablist" aria-label="文章目录视图">
          <button
            v-for="item in VIEW_OPTIONS"
            :key="item.id"
            type="button"
            class="article-view-button"
            :class="{ active: activeView === item.id }"
            role="tab"
            :aria-selected="activeView === item.id"
            @click="setView(item.id)"
          >
            <strong>{{ item.label }}</strong>
            <span>{{ item.english }}</span>
          </button>
        </div>

        <label class="article-search">
          <span class="article-search__label">Search the issue</span>
          <span class="article-search__field">
            <input
              v-model="searchQuery"
              type="search"
              placeholder="搜索标题、摘要或标签"
              autocomplete="off"
            >
            <button v-if="searchQuery" type="button" @click="clearSearch">清除</button>
          </span>
        </label>
      </div>

      <div class="article-directory-meta rv" aria-live="polite">
        <span>{{ resultLabel }}</span>
        <button
          v-if="searchQuery || selectedTag !== '全部'"
          type="button"
          @click="clearAllFilters"
        >
          清除筛选
        </button>
      </div>

      <p v-if="error" class="feedback print-feedback rv">{{ error }}</p>
      <div v-else-if="loading" class="posts-skeleton" aria-busy="true" aria-label="目录整理中">
        <div v-for="n in 4" :key="n" class="posts-skeleton__item">
          <div class="sk-line sk-line--sm"></div>
          <div class="sk-line sk-line--lg"></div>
          <div class="sk-line sk-line--md"></div>
        </div>
      </div>
      <p v-else-if="!visiblePosts.length" class="feedback print-feedback rv">
        没有找到符合条件的文章，请调整关键词或筛选条件。
      </p>

      <div v-else-if="activeView === 'latest'" class="article-list print-article-list unified-latest-list">
        <RouterLink
          v-for="(post, index) in visiblePosts"
          :key="post.slug"
          :to="`/posts/${post.slug}`"
          class="article-item print-list-item rv"
          :data-reveal-delay="Math.min(index, 8) * 45"
        >
          <div class="article-meta">
            <span>{{ displayDate(post.published_at) }}</span>
            <span>{{ post.read_time }}</span>
          </div>
          <h2>{{ post.title }}</h2>
          <p>{{ post.excerpt || "这篇文章暂时还没有摘要。" }}</p>
          <div class="post-card-tags list-tags">
            <span v-for="tag in post.tags" :key="tag" class="tag tag--code">{{ tag }}</span>
          </div>
        </RouterLink>
      </div>

      <div v-else-if="activeView === 'archive'" class="print-year-ledger unified-archive-view">
        <section
          v-for="([year, items], index) in groupedPosts"
          :key="year"
          class="archive print-year-block rv"
          :data-reveal-delay="index * 60"
        >
          <div class="archive__year">
            <span>{{ year }}</span>
            <strong>{{ items.length }} 篇</strong>
          </div>
          <ul class="archive__list">
            <li v-for="post in items" :key="post.slug" class="archive__li">
              <span class="archive__date">{{ shortDate(post.published_at) }}</span>
              <RouterLink :to="`/posts/${post.slug}`" class="archive__title">{{ post.title }}</RouterLink>
              <span class="archive__tags">
                <span v-for="tag in post.tags?.slice(0, 2)" :key="tag" class="tag tag--code">{{ tag }}</span>
              </span>
            </li>
          </ul>
          <div v-if="index < groupedPosts.length - 1" class="orn">✦</div>
        </section>
      </div>

      <div v-else class="unified-tags-view">
        <div class="tag-filter-row print-tag-cloud rv" role="list" aria-label="标签筛选">
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

        <div class="g2e print-tag-results">
          <RouterLink
            v-for="(post, index) in visiblePosts"
            :key="post.slug"
            :to="`/posts/${post.slug}`"
            class="art print-article-strip rv"
            :data-reveal-delay="Math.min(index, 6) * 50"
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
      </div>

      <span class="pg pg--r">— Article Index —</span>
    </section>
  </div>
</template>
