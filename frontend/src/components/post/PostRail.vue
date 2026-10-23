<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import { shortDate } from "../../composables/useFormat";
import { usePanelPin } from "../../composables/usePanelPin";
import { usePersistedCollapse } from "../../composables/usePersistedCollapse";
import { groupByYear } from "../../lib/postGroups";

/**
 * 文章页左侧清单：当前栏目的编年索引。
 *
 * 它住在阅读版式左边那条本来空置的 1fr 轨道里，并且贴左边缘对齐 —— 与右侧目录
 * 贴右边缘对称。这样折叠与否只改变自己的宽度，正文轨道的中心与宽度都不动，
 * 也就不会出现「折叠侧栏时文字在读者眼皮底下重排」。
 *
 * 高度上它与那条网格行解耦：外层 aside 高 0、不参与行高计算，展开态与书脊都由
 * 内部绝对定位撑开（见 post.css）。副作用是面板在到达吸附位置之前从行的顶部开始排，
 * 因此还得把「它自己顶部到视口底部」的剩余空间同步给 CSS，否则底部（含「完整目录」）
 * 会被屏幕裁掉，看起来像清单比左栏还长。越过吸附线后改由 .is-pinned 换成 fixed，
 * 滚动过程中不再写任何坐标（理由见 usePanelPin.js）。
 *
 * 行只给日期 + 标题：约 300px 宽放不下摘要，摘要留给 /posts 的索引。
 */
const props = defineProps({
  posts: { type: Array, required: true },
  total: { type: Number, default: 0 },
  hasMore: { type: Boolean, default: false },
  loadingMore: { type: Boolean, default: false },
  mode: { type: String, default: "category" },
  category: { type: String, default: "" },
  // 当前文章所属栏目（「本栏目」这一项的落点）。它和 category 不是一回事：
  // 本栏目太薄而清单退化为「最新」时 category 是空的，但读者仍然应该能选回本栏目。
  followCategory: { type: String, default: "" },
  categories: { type: Array, default: () => [] },
  currentSlug: { type: String, default: "" },
});

const emit = defineEmits(["more", "select-scope"]);

const menuRef = ref(null);
const scopeButtonRef = ref(null);

// 展开态是默认：折起来虽然干净，但先折起来等于让人永远发现不了这一栏。
const { collapsed, collapse, expand } = usePersistedCollapse("zhizhi-article-rail-collapsed");

const navigationRef = ref(null);
const hostRef = ref(null);
const menuOpen = ref(false);
let alignmentFrame = 0;
let resizeAlignmentTimer = 0;
const { pinned, parked } = usePanelPin(hostRef);

const groups = computed(() => groupByYear(props.posts));
const currentIndex = computed(() => props.posts.findIndex((post) => post.slug === props.currentSlug));
const allHref = computed(() => (
  props.mode === "category" && props.category
    ? `/posts?cat=${encodeURIComponent(props.category)}`
    : "/posts"
));

// 表头与勾选都读「当前装载的范围」，而不是读读者的选择状态：本栏目太薄时清单会
// 退化为全站最新，此时标签必须写实（最新），菜单里再说明本栏目为什么只剩自己。
const scopeLabel = computed(() => (
  props.mode === "latest" ? "最新" : props.category || "全部"
));

/**
 * 清单范围的可选项：本栏目 / 全站最新 / 其余栏目。
 *
 * 为什么做成菜单而不是一排胶囊：栏目会随写作增加，铺开就把这一栏变成第二个筛选条，
 * 而左栏只有 280px 上下。菜单默认收起，只占表头那一个词的位置——读者需要时才展开。
 *
 * 「本栏目」这一项发出的 key 是栏目名而不是「跟随」：读者明确点了它，就不该再被
 * 「本栏目太薄→退化为最新」这条默认策略顶掉；默认策略只作用于初次进入。
 */
const scopeOptions = computed(() => {
  const options = [];
  const follow = props.followCategory;
  const list = (props.categories || []).map((item) => (
    typeof item === "string" ? { name: item, count: 0 } : item
  ));
  const categories = list.filter((item) => item?.name);

  if (follow) {
    const count = Number(categories.find((item) => item.name === follow)?.count) || 0;
    options.push({
      key: follow,
      label: `本栏目 · ${follow}`,
      // 读者要能看出「本栏目」与「最新」的差别：本栏目只有当前这一篇时清单里就只剩
      // 自己，这里提前说明，免得点开才发现。
      hint: count > 1 ? String(count) : "仅此一篇",
      active: props.mode === "category" && props.category === follow,
    });
  }
  options.push({
    key: "latest",
    label: "最新",
    hint: "全站",
    active: props.mode === "latest",
  });
  for (const item of categories) {
    if (item.name === follow) continue;
    options.push({
      key: item.name,
      label: item.name,
      hint: item.count ? String(item.count) : "",
      active: props.mode === "category" && props.category === item.name,
    });
  }
  return options;
});

async function toggleMenu() {
  if (menuOpen.value) {
    closeMenu();
    return;
  }
  menuOpen.value = true;
  // 菜单声明了 role="menu"，就必须兑现键盘模型：打开即焦点落在当前项上，
  // 之后方向键在选项间移动（见 handleKeydown）。此前只切换了 aria-expanded，
  // 焦点仍留在触发器上，方向键毫无反应——承诺了却没实现。
  await nextTick();
  const target = menuRef.value?.querySelector('[role="menuitemradio"][aria-checked="true"]')
    || menuRef.value?.querySelector('[role="menuitemradio"]');
  target?.focus();
}

function closeMenu(options) {
  // 这个函数也被 watch(() => props.currentSlug, closeMenu) 直接当回调用，
  // 拿到的是 slug 字符串（可能是 null），不能按对象解构。
  const restoreFocus = options === true || options?.restoreFocus === true;
  menuOpen.value = false;
  if (restoreFocus) scopeButtonRef.value?.focus();
}

function chooseScope(option) {
  menuOpen.value = false;
  scopeButtonRef.value?.focus();
  if (!option.active) emit("select-scope", option.key);
}

function handleKeydown(event) {
  if (!menuOpen.value) return;

  if (event.key === "Escape") {
    event.preventDefault();
    closeMenu({ restoreFocus: true });
    return;
  }

  const buttons = Array.from(menuRef.value?.querySelectorAll('[role="menuitemradio"]') || []);
  if (!buttons.length) return;
  const index = buttons.indexOf(document.activeElement);

  if (event.key === "ArrowDown") {
    event.preventDefault();
    buttons[(index + 1 + buttons.length) % buttons.length]?.focus();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    buttons[index <= 0 ? buttons.length - 1 : index - 1]?.focus();
  } else if (event.key === "Home") {
    event.preventDefault();
    buttons[0]?.focus();
  } else if (event.key === "End") {
    event.preventDefault();
    buttons[buttons.length - 1]?.focus();
  } else if (event.key === "Tab") {
    // Tab 是「我要离开这个菜单」，把菜单收起但把焦点交给浏览器继续走。
    closeMenu();
  }
}

function handleOutside(event) {
  if (!event.target.closest?.(".article-rail__head")) closeMenu();
}

watch(menuOpen, (open) => {
  if (open) {
    document.addEventListener("pointerdown", handleOutside);
    document.addEventListener("keydown", handleKeydown);
  } else {
    document.removeEventListener("pointerdown", handleOutside);
    document.removeEventListener("keydown", handleKeydown);
  }
});

watch(() => props.currentSlug, closeMenu);

function pad(value) {
  return String(value).padStart(2, "0");
}

/**
 * 把当前篇滚进清单自己的可视区。
 *
 * 不用平滑滚动：清单在换篇时是整体重建的，一次动画滚动会在正文刚切换的同时
 * 让栏内文字横冲过去。只在真的越界时才动，避免每次挂载都把列表微调一下。
 */
function alignActiveRow() {
  alignmentFrame = 0;
  const navigation = navigationRef.value;
  const active = navigation?.querySelector(".is-current");
  if (!navigation || !active) return;

  const navigationRect = navigation.getBoundingClientRect();
  const activeRect = active.getBoundingClientRect();
  const edgeMargin = 12;

  if (activeRect.top < navigationRect.top + edgeMargin) {
    navigation.scrollTop += activeRect.top - navigationRect.top - edgeMargin;
  } else if (activeRect.bottom > navigationRect.bottom - edgeMargin) {
    navigation.scrollTop += activeRect.bottom - navigationRect.bottom + edgeMargin;
  }
}

async function scheduleAlignment() {
  if (collapsed.value) return;
  await nextTick();
  if (alignmentFrame) window.cancelAnimationFrame(alignmentFrame);
  alignmentFrame = window.requestAnimationFrame(alignActiveRow);
}

/**
 * 视口变矮后清单可视区也变矮，当前篇可能落到可视区之外——挂载时对齐过一次
 * 并不够，所以随 resize 再对齐（与右侧目录同一套做法）。
 */
async function handleResize() {
  await scheduleAlignment();
  window.clearTimeout(resizeAlignmentTimer);
  resizeAlignmentTimer = window.setTimeout(() => {
    resizeAlignmentTimer = 0;
    scheduleAlignment();
  }, 320);
}

watch(
  [() => props.posts.length, () => props.currentSlug, collapsed],
  scheduleAlignment,
  { flush: "post" },
);

onMounted(() => {
  window.addEventListener("resize", handleResize, { passive: true });
  scheduleAlignment();
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleResize);
  window.clearTimeout(resizeAlignmentTimer);
  if (alignmentFrame) window.cancelAnimationFrame(alignmentFrame);
});
</script>

<template>
  <aside
    ref="hostRef"
    id="article-rail-panel"
    class="article-rail"
    :class="{ 'is-collapsed': collapsed, 'is-parked': parked, 'is-pinned': pinned }"
    aria-label="文章清单"
  >
    <!-- 折叠态：贴左边缘的竖排书脊，点一下展开 -->
    <button
      v-if="collapsed"
      class="article-rail__spine"
      type="button"
      aria-expanded="false"
      aria-controls="article-rail-panel"
      title="展开文章清单"
      @click="expand"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
      <span class="article-rail__spine-label">文章清单</span>
    </button>

    <div v-else class="article-rail__body">
      <div class="article-rail__head">
        <button
          ref="scopeButtonRef"
          class="article-rail__scope"
          type="button"
          aria-haspopup="menu"
          :aria-expanded="menuOpen ? 'true' : 'false'"
          :title="`切换清单范围（当前：${scopeLabel}）`"
          @click="toggleMenu"
        >
          <span>{{ scopeLabel }}</span>
          <svg class="article-rail__scope-caret" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </button>
        <strong v-if="currentIndex >= 0">{{ currentIndex + 1 }}<i>/{{ total }}</i></strong>
        <strong v-else>{{ pad(total) }}</strong>
        <button
          class="article-rail__toggle"
          type="button"
          aria-expanded="true"
          aria-controls="article-rail-panel"
          title="收起文章清单"
          @click="collapse"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" /></svg>
        </button>

        <div
          v-if="menuOpen"
          ref="menuRef"
          class="article-rail__scopes"
          role="menu"
          aria-label="清单范围"
        >
          <button
            v-for="option in scopeOptions"
            :key="option.key || 'follow'"
            type="button"
            role="menuitemradio"
            class="article-rail__scope-option"
            :class="{ 'is-active': option.active }"
            :aria-checked="option.active ? 'true' : 'false'"
            @click="chooseScope(option)"
          >
            <span>{{ option.label }}</span>
            <em v-if="option.hint">{{ option.hint }}</em>
          </button>
        </div>
      </div>

      <nav ref="navigationRef" aria-label="文章清单导航">
        <template v-for="([year, items]) in groups" :key="year">
          <p class="article-rail__year">{{ year }}</p>
          <RouterLink
            v-for="post in items"
            :key="post.slug"
            :to="`/posts/${post.slug}`"
            class="article-rail__row"
            :class="{ 'is-current': post.slug === currentSlug }"
          >
            <span class="article-rail__date">{{ shortDate(post.published_at) }}</span>
            <em>{{ post.title }}</em>
          </RouterLink>
        </template>

        <button
          v-if="hasMore"
          class="article-rail__more"
          type="button"
          :disabled="loadingMore"
          @click="$emit('more')"
        >
          {{ loadingMore ? "加载中……" : "加载更多" }}
        </button>
      </nav>

      <RouterLink class="article-rail__all" :to="allHref">
        <span>完整目录</span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5l7 7-7 7" /></svg>
      </RouterLink>
    </div>
  </aside>
</template>
