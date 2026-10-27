<script setup>
// 关于页（DESIGN.md §5.4）：页头「关于」通栏（与其他页同构），其下三栏书案——
// 主卷 --col-read 宽（楷体导语 + 正文），右栏是联系方式 <dl> 与「更新日历」。
// 更新日历是 GitHub 风格热力图：近 26 周按日聚合「文章 + 余笺」的发布次数，
// 客户端取最近各 50 条聚合，零新增后端接口。不使用卡片。

import { computed, onMounted, ref } from "vue";

import AsyncState from "../components/AsyncState.vue";
import { useSite } from "../composables/useSite";
import { getNotes, getPosts } from "../services/api";

const { site, ensureSite, loading, error } = useSite();

const introParagraphs = computed(() => {
  const paragraphs = site.value?.about_intro || [];
  if (paragraphs.length) return paragraphs;
  return [
    "至知是一份持续更新的个人博客，用来整理技术实践、项目复盘、阅读笔记和那些值得反复回看的问题。",
  ];
});
const contactLinks = computed(() => site.value?.social_links || []);

/* ---------- 更新日历：近 CALENDAR_WEEKS 周按日聚合 ---------- */

const CALENDAR_WEEKS = 26;
const ACTIVITY_FETCH_LIMIT = 50; // 文章与余笺各取最近 50 条，个人站足够覆盖半年窗

const activity = ref({}); // "YYYY-MM-DD" -> 次数
const calendarError = ref(false);

const today = (() => {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
})();

function dateKey(date) {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/** 列从周日开始：先补齐到本周末，再回退 CALENDAR_WEEKS 周；超出今天的格子不渲染颜色。 */
const calendar = computed(() => {
  const end = new Date(today);
  end.setDate(end.getDate() + (6 - end.getDay()));
  const start = new Date(end);
  start.setDate(start.getDate() - (CALENDAR_WEEKS * 7 - 1));

  const columns = [];
  const cursor = new Date(start);
  for (let week = 0; week < CALENDAR_WEEKS; week += 1) {
    const days = [];
    for (let i = 0; i < 7; i += 1) {
      const day = new Date(cursor);
      const key = dateKey(day);
      days.push({ key, count: activity.value[key] || 0, future: day > today });
      cursor.setDate(cursor.getDate() + 1);
    }
    columns.push(days);
  }

  const total = columns.reduce(
    (sum, days) => sum + days.reduce((s, d) => s + d.count, 0),
    0,
  );
  return { columns, total };
});

/** GitHub 式五档：0 无更新，墨色随次数加深（color-mix 于 --ink / --paper-sunk）。 */
function levelOf(count) {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count === 2) return 2;
  if (count <= 4) return 3;
  return 4;
}

async function loadActivity() {
  try {
    const [postsList, notesList] = await Promise.all([
      getPosts({ limit: ACTIVITY_FETCH_LIMIT }),
      getNotes({ limit: ACTIVITY_FETCH_LIMIT }),
    ]);
    const counts = {};
    for (const item of [...(postsList?.items || []), ...(notesList?.items || [])]) {
      const key = String(item?.published_at || "").slice(0, 10);
      if (/^\d{4}-\d{2}-\d{2}$/.test(key)) counts[key] = (counts[key] || 0) + 1;
    }
    activity.value = counts;
  } catch {
    // 日历拉不到时退回空图，不影响版面与联系方式
    calendarError.value = true;
  }
}

async function retrySite() {
  try {
    await ensureSite({ force: true });
  } catch (err) {
    // 错误态仍由 AsyncState 呈现
  }
}

onMounted(async () => {
  loadActivity();
  try {
    await ensureSite();
  } catch (err) {
    // 错误态由 AsyncState 呈现
  }
});
</script>

<template>
  <div class="about-view">
    <AsyncState
      v-if="loading && !site"
      loading
      loading-message="正在加载…"
    />
    <AsyncState
      v-else-if="error && !site"
      :error="error"
      empty-message="请检查网络后重试。"
      @retry="retrySite"
    />

    <template v-else>
      <header class="about-head">
        <h1>关于</h1>
      </header>

      <div class="page-grid">
        <div class="page-grid__main">
          <div class="about-lead">
            <p v-for="paragraph in introParagraphs" :key="paragraph">{{ paragraph }}</p>
          </div>

          <section class="prose">
            <p v-if="site?.summary">{{ site.summary }}</p>
          </section>
        </div>

        <aside class="page-grid__side page-grid__side--sticky about-side">
          <section v-if="contactLinks.length" class="side-block">
            <header class="side-block__head">
              <h2 class="side-block__title">联系方式</h2>
            </header>
            <dl class="about-contact">
              <template v-for="item in contactLinks" :key="item.label">
                <dt>{{ item.label }}</dt>
                <dd>
                  <a class="text-link" :href="item.url" target="_blank" rel="noreferrer">{{ item.value }}</a>
                </dd>
              </template>
            </dl>
          </section>

          <section class="side-block" aria-label="更新日历">
            <header class="side-block__head">
              <h2 class="side-block__title">更新日历</h2>
              <span class="side-block__sub">{{ calendar.total }} 次</span>
            </header>
            <div
              v-if="!calendarError"
              class="about-calendar"
              role="img"
              :aria-label="`近 ${CALENDAR_WEEKS} 周更新 ${calendar.total} 次`"
            >
              <div v-for="(week, wi) in calendar.columns" :key="wi" class="about-calendar__col">
                <span
                  v-for="day in week"
                  :key="day.key"
                  class="about-calendar__cell"
                  :class="[
                    `about-calendar__cell--l${levelOf(day.count)}`,
                    { 'about-calendar__cell--off': day.future },
                  ]"
                  :title="day.future ? undefined : `${day.key} · ${day.count ? `${day.count} 次更新` : '无更新'}`"
                ></span>
              </div>
            </div>
            <p v-else class="side-block__empty">更新日历暂时无法加载。</p>
            <p class="about-calendar__legend" aria-hidden="true">
              <span>少</span>
              <span class="about-calendar__cell"></span>
              <span class="about-calendar__cell about-calendar__cell--l1"></span>
              <span class="about-calendar__cell about-calendar__cell--l2"></span>
              <span class="about-calendar__cell about-calendar__cell--l3"></span>
              <span class="about-calendar__cell about-calendar__cell--l4"></span>
              <span>多</span>
              <span class="about-calendar__range">近 {{ CALENDAR_WEEKS }} 周</span>
            </p>
          </section>
        </aside>
      </div>
    </template>
  </div>
</template>
