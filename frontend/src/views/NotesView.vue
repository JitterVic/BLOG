<script setup>
// 余笺列表（DESIGN.md §5.3）：按年份分组的编年索引 + 类型筛选（URL 为唯一状态源）。
// 三栏书案：右栏是「项目与作品外链」精选 + 最近更新的文章，方便随手记读者切回长文。

import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import AsyncState from "../components/AsyncState.vue";
import { shortDate } from "../composables/useFormat";
import { NOTE_TYPES, useNotes } from "../composables/useNotes";
import { setPageMeta } from "../composables/usePageMeta";
import { useTitleMorph } from "../composables/useTitleMorph";
import { groupByYear } from "../lib/postGroups";
import { getPosts } from "../services/api";

const route = useRoute();
const router = useRouter();
const { notes, total, error, loading, loadNotes } = useNotes();
const { handleOpen } = useTitleMorph();

const selectedType = computed(() => {
  const raw = typeof route.query.type === "string" ? route.query.type : "";
  return NOTE_TYPES.some((item) => item.value === raw) ? raw : "";
});
const selectedTypeLabel = computed(() => {
  const found = NOTE_TYPES.find((item) => item.value === selectedType.value);
  return found && found.value ? found.label : "";
});
const subtitle = computed(() => {
  if (selectedTypeLabel.value) return `类型：${selectedTypeLabel.value}，共 ${total.value} 条`;
  return `共 ${total.value} 条`;
});
const groupedNotes = computed(() => groupByYear(notes.value));

/** 项目 / 作品精选：带外链或属于项目/作品类型的余笺，最多 5 条。 */
const projectNotes = computed(() =>
  notes.value
    .filter((note) => note.external_url || note.type === "project" || note.type === "work")
    .slice(0, 5),
);

const latestPosts = ref([]);
let postsController = null;

async function loadLatestPosts() {
  postsController?.abort();
  postsController = new AbortController();
  try {
    const list = await getPosts({ sort: "latest", limit: 5, signal: postsController.signal });
    latestPosts.value = Array.isArray(list?.items) ? list.items : [];
  } catch {
    // 右栏「最近文章」加载失败不阻塞余笺列表
    latestPosts.value = [];
  }
}

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function selectType(type) {
  router.replace({ name: "notes", query: type ? { type } : {} });
}

async function load() {
  await loadNotes({ type: selectedType.value, limit: 20 });
}

setPageMeta({ title: "余笺 · 至知", description: "记下那些尚未必要成为文章的事。" });
onMounted(() => {
  load();
  loadLatestPosts();
});
watch(selectedType, load);
</script>

<template>
  <div class="notes-view">
    <header class="notes-head">
      <h1>余笺</h1>
      <p class="notes-head__intro">记下那些尚未必要成为文章的事。</p>
      <p class="posts-head__sub">
        <span>{{ subtitle }}</span>
      </p>
      <!-- 窄屏类型条（≥1100px 由左栏「余笺类型」承担，CSS 隐去） -->
      <nav class="notes-types" aria-label="余笺类型">
        <button
          v-for="item in NOTE_TYPES"
          :key="item.value || 'all'"
          type="button"
          class="notes-types__link"
          :aria-pressed="selectedType === item.value"
          @click="selectType(item.value)"
        >
          <span class="marker-sweep" :class="{ 'is-on': selectedType === item.value }">{{ item.label }}</span>
        </button>
      </nav>
    </header>

    <div class="page-grid">
      <div class="page-grid__main">
        <AsyncState v-if="error" :error="error" empty-message="请检查网络后重试。" @retry="load" />
        <AsyncState v-else-if="loading && !notes.length" loading variant="rows" loading-message="正在加载…" />

        <!-- 已有数据再次筛选时保留列表 DOM，只降不透明度（§5.3） -->
        <div v-else-if="notes.length" class="notes-list" :class="{ 'list-refreshing': loading }">
          <Transition name="list-swap">
            <div :key="selectedType">
              <section
                v-for="[year, items] in groupedNotes"
                :key="year"
                class="notes-year"
                :aria-label="`${year} 年`"
              >
                <h2 class="notes-year__head">{{ year }}</h2>
                <article v-for="note in items" :key="note.slug" class="note-row">
                  <time class="note-row__date" :datetime="note.published_at">{{ shortDate(note.published_at) }}</time>
                  <div class="note-row__main">
                    <h3 class="note-row__title">
                      <RouterLink
                        class="note-row__link"
                        :to="{ name: 'note', params: { slug: note.slug } }"
                        @click="handleOpen($event, { name: 'note', params: { slug: note.slug } })"
                      >{{ note.title }}</RouterLink>
                    </h3>
                    <p v-if="note.excerpt" class="note-row__excerpt">{{ note.excerpt }}</p>
                  </div>
                  <span class="note-row__type">{{ note.type_label }}</span>
                </article>
              </section>
              <p class="notes-total">已经到底了，共 {{ total }} 条。</p>
            </div>
          </Transition>
        </div>
        <p v-else class="home-section__empty">这里还没有余笺。</p>
      </div>

      <!-- 右辅栏：项目与作品外链 + 最近文章 -->
      <aside class="page-grid__side page-grid__side--sticky notes-side">
        <section v-if="projectNotes.length" class="side-block" aria-label="项目与作品">
          <header class="side-block__head">
            <h2 class="side-block__title">项目与作品</h2>
          </header>
          <ul class="side-compact-list">
            <li v-for="note in projectNotes" :key="note.slug">
              <p v-if="hostOf(note.external_url)" class="side-compact-list__meta">{{ hostOf(note.external_url) }}</p>
              <p v-else-if="note.type_label" class="side-compact-list__meta">{{ note.type_label }}</p>
              <RouterLink
                class="side-compact-list__link"
                :to="{ name: 'note', params: { slug: note.slug } }"
                @click="handleOpen($event, { name: 'note', params: { slug: note.slug } })"
              >{{ note.title }}</RouterLink>
            </li>
          </ul>
        </section>

        <section v-if="latestPosts.length" class="side-block" aria-label="最近文章">
          <header class="side-block__head">
            <h2 class="side-block__title">最近文章</h2>
            <RouterLink class="side-block__sub text-link" :to="{ name: 'posts' }">全部</RouterLink>
          </header>
          <ul class="side-compact-list">
            <li v-for="post in latestPosts" :key="post.slug">
              <p class="side-compact-list__meta">
                <time :datetime="post.published_at">{{ shortDate(post.published_at) }}</time>
                <span v-if="post.category">{{ post.category }}</span>
              </p>
              <RouterLink
                class="side-compact-list__link"
                :to="{ name: 'post', params: { slug: post.slug } }"
                @click="handleOpen($event, { name: 'post', params: { slug: post.slug } })"
              >{{ post.title }}</RouterLink>
            </li>
          </ul>
        </section>
      </aside>
    </div>
  </div>
</template>
