# Article Page Marginalia Rail and Panel Collapse Design

Date: 2026-10-15
Status: Implemented and verified on 2026-10-15

## Context

The article reading page (`/posts/:slug`) uses a viewport-wide symmetric three-track grid:

```
minmax(0, 1fr) | minmax(0, 760px) | minmax(0, 1fr)
      ".       |      article     |      toc"
```

At 1920px the layout resolves to 580px / 760px / 580px. The article keeps the viewport center and the
760px width no matter what the side panels do (this was an approved correction on 2026-08-12, because
an earlier `article + gap + TOC` grid pushed the reading column off center and clipped wide code
surfaces).

Two consequences of that decision are visible today:

1. **The left rail is completely empty.** The TOC occupies the right rail (right-aligned, hugging the
   viewport edge, 220px wide). The left rail holds nothing, so ~580px of horizontal space is unused
   while the reader has no way to move to a sibling article without leaving the page and losing their
   place.
2. **The right rail is the only panel, and it cannot get out of the way.** Readers who want an
   uncluttered page have no option, and between 1281px and ~1500px the TOC and the article compete for
   the remaining track.

The 编年索引 (year-grouped chronological index) is the site's single archive form, and 栏目
(`taxonomy.CATEGORY_PRESETS`) is the only facet the front-end filters by. The article page already
extends that model after the fact: `PostSequenceNav` (previous/next) and `RelatedPostsGrid` (2 related
posts) both live *after* the article body, so they are only reachable once the reader has scrolled to
the very bottom.

## Goals

- Fill the empty left rail with a 文章清单 that lets the reader switch to a sibling article without
  leaving the reading page.
- Make the rail's ordering meaningful: the current article's 栏目, in the same 编年索引 form used by
  `/posts`.
- Let both side panels collapse (rail to the left, TOC to the right) and remember that choice.
- **Collapsing or expanding a panel must not move the reading column.** No horizontal reflow of the
  text, no scroll-anchor jump.
- No new public API shape, no schema change, no change to `/posts`.
- Keep the change frontend-only.

## Non-goals

- A second archive browser in the rail: no search box, no category chip row, no tag filtering, no
  independent pagination UI beyond a bounded "加载更多". Browsing the whole archive stays `/posts`.
- Widening or narrowing the 760px reading column. Collapsing a panel must not change the text width
  (that would move text under the reader's eyes); a separate "宽版" toggle is deliberately out of scope.
- A mobile/tablet form for the rail. Below 1360px the article page keeps today's layout exactly.
- Collapsing the narrow-screen horizontal TOC strip: it is already compact.
- Fixing `RouterLink`'s inclusive-match `aria-current` on other components (`PostSequenceNav`,
  `ArchiveLedger`). The rail handles its own rows correctly; the rest is pre-existing and untouched.

## Alternatives Considered

**A. Rail lives in the existing empty left track; panels stay edge-aligned (recommended).**
The rail becomes a grid item in the left `1fr` track with `justify-self: start`, exactly mirroring how
the TOC sits in the right track with `justify-self: end`. The three tracks stay symmetric, so the
article column's position and width are independent of both panels. Toggling a panel only changes that
panel's own width. Zero reading-column movement, minimal CSS, and the marginalia read as a deliberate
editorial device on both sides.

**B. Give each panel its own fixed track (`rail / article / toc`).**
The panels would feel attached to the article and could hold more content. Rejected: the article's x
position then depends on which panels are open, so every toggle reflows the text and can jump the
scroll position. It also breaks the symmetric-track invariant that the 2026-08-12 correction
established.

**C. Fixed-position overlay drawer that slides over the content.**
Cheap and width-independent. Rejected: it covers the text (needs a scrim, hurts reading), and at
≥1360px there is already free space on both sides, so overlaying buys nothing. It also reads as an app
affordance rather than a printed-page one.

## Selected Approach

### 1. Rail placement: fill the empty left rail, keep the tracks symmetric

`.post-reading-layout` keeps `grid-template-columns: minmax(0, 1fr) minmax(0, var(--post-article-width)) minmax(0, 1fr)`
and gains a fourth area arrangement. New tokens are declared on `.post-reading-layout` (not on the
panel), for the same custom-property scoping reason that already governs the TOC offsets — panel
siblings cannot read properties declared on each other:

```css
.post-reading-layout {
  --post-rail-width: 19.5rem;                      /* 312px */
  --post-rail-gap: clamp(1.25rem, 2vw, 2.25rem);
  grid-template-areas: "rail article toc";
}
.post-reading-layout--no-toc                      { grid-template-areas: "rail article .";   }
.post-reading-layout--no-rail                     { grid-template-areas: ".   article toc";  }
.post-reading-layout--no-toc.post-reading-layout--no-rail { grid-template-areas: ". article ."; }
```

`.article-rail` mirrors `.article-toc`: `grid-area: rail`, `justify-self: start`, `position: sticky`,
`top: 6.8rem`, `overflow: visible` with an inner scrolling `nav`,
`margin-left: clamp(0.5rem, 1vw, 1.5rem)`, `width: min(var(--post-rail-width), calc(100% - var(--post-rail-gap)))`,
and a transparent background. The `min()` bound is the load-bearing part: the panel can never grow into
the article track, at any width, whatever the viewport does.

Its height and vertical position, however, must **not** mirror the TOC's original
`position: sticky; max-height: calc(100vh - 8.5rem)` recipe, and neither may the TOC's own.

**Height.** The rail is a grid item, so its box height participates in the row's height: a 30-row
list (944px measured) next to a single-paragraph article added ~700px of empty column beneath the
text, and collapsing it shrank the document enough that the browser clamped the reader's scroll
position (scrollY 1400 → 1201). Capping the panel by the article body only traded that for a crippled
list (38 rows in a 217px box, ~3 rows visible). So the rail's box is decoupled from the row:
`height: 0` on `.article-rail`, with the expanded panel (`.article-rail__body`) and the collapsed
spine (`.article-rail__spine`) `position: absolute; top: 0; left: 0; width: 100%` inside it. The
document height is then independent of both panels.

**Position.** Both panels are `position: absolute` grid children, which makes each one's containing
block its own grid area — so `--panel-shift` can be a plain "distance from the top of my area", and
percentage widths still resolve against the track. `position: sticky` cannot be used here: sticky
only allows the panel to sit *within* its grid area, and the area's height is decided by the article
body (the rail deliberately does not contribute to it, and the TOC is shorter than any real article).
On a short article the area scrolls by within ~200px, and sticky drags the panel up with it — the
panel's top slid from 109 to **-193** in a 700px-high window with a 217px article, taking the collapse
button under the fixed header and then off-screen entirely ("collapsed and now it won't open").

`usePanelPin.js` therefore computes, on every scroll/resize:

- `--panel-shift` = `max(areaTop, 6.8rem) - areaTop` — the panel follows the reading area in, then
  stays pinned under the fixed header;
- `--panel-avail` = `min(viewportHeight - top - 8, areaBottom - top)` — the panel never exceeds the
  viewport, and shrinks instead of spilling over whatever follows the reading area;
- `is-parked` when that room drops below 96px, i.e. the area has effectively been read past — the
  panel is hidden rather than left as an unclickable sliver.

Entering the area the panel grows from the bottom edge; once pinned both panels sit at the same line
and keep the same height for the whole article. Verified on a short article (700px window) and a long
one (1080p/900p): panels always inside the viewport, toggles and spines always hit-testable, article
column unmoved.

Clearance check at the narrow end (1440px, the rail's breakpoint): track 340px,
`--post-rail-gap` = 28.8px, so width = min(312, 311.2) = 311.2px, `margin-left` = 14.4px →
the rail spans 14.4 → 325.6px and the article track starts at 340px. At 1920px: rail 14 → 326px
(312 wide), article 575 → 1335px, TOC 1656 → 1896px — the two panels hug their viewport edges with
visually equal insets, which is the look the right-hand TOC already has.

Below 1440px the rail is not laid out at all. This must be enforced in CSS, not only in JS: at
≤1280px `.post-reading-layout` collapses to a single column with `grid-template-areas: "toc" "article"`,
and an *unhidden* rail item would be auto-placed into an implicit row and appear in the stacked
layout. So the base rule is `display: none` and the `@media (min-width: 1440px)` block switches it to
`block`. A `display: none` element is not a grid item, so the ≤1280px block needs no change. The
`matchMedia` gate in `PostView` uses the same 1440px value, otherwise the component would render and
fetch a list that CSS hides.

### 2. Rail content: the current 栏目's 编年索引

- Data: `GET /api/posts?category=<栏目>&page=1&limit=30`, one request, resolved through the existing
  `usePosts` composable. Response already carries `total` and `has_more`.
- Scope label: the 栏目 name plus the total count. Rows are date + title (two-line clamp). No excerpt:
  at ~270px an excerpt is noise, and the rail is a locator, not the index. `/posts` keeps the excerpts.
- Grouping: the same year grouping as `/posts`, extracted into `lib/postGroups.js` and shared with
  `PostsView.vue` instead of being written twice.
- Current article: the matching row is marked `is-current` by `slug` comparison and scrolled into view
  on load and on article switch, reusing the same "keep the active entry visible" alignment that
  `PostToc` performs vertically.
- Deep-article fallback: if the current slug is not inside the loaded page (possible for an old article
  in a large 栏目), the rail renders a pinned 当前篇 row above the list instead of pretending there is
  no current position. Position readout (`12/48`) is shown only when the row is actually in the list.
- Empty-scope fallback (threshold: fewer than 3 published posts, i.e. the current article plus at most
  one other): if the current 栏目 is below it, the scope falls back to the site-wide latest list and the
  head label becomes 最新. If the fallback scope is also below it, the rail is not rendered at all —
  there is nothing to switch to.
- Footer: 完整目录 → `/posts?category=<栏目>`, so the deep archive stays in one place.
- 加载更多 appears only when the server reports `has_more`.

Rows are plain `<RouterLink>` elements. Verified against the installed router
(`vue-router/dist/vue-router.mjs`): `aria-current` is only emitted when `isExactActive`, so exactly one
row — the current article — gets `aria-current="page"` and the rest get none. What the router *does*
add to every row is the inclusive `router-link-active` class (all `/posts/:slug` links share the `post`
route record), so the current-row style keys off an explicit `is-current` class instead of the
router's own classes.

### 3. Data layer: one cached singleton, no refetch per article

`PostView` is destroyed and recreated on every slug change (`:key="viewRoute.fullPath"`), so a
component-local list would refetch and flash on every switch. `usePostRail` is therefore a
module-scoped singleton, like `useSite`:

- wraps `usePosts` inside a detached `effectScope(true)` — `usePosts` registers `onScopeDispose`, which
  warns when called with no active scope; the detached scope owns that cleanup for the page's lifetime;
- caches the resolved list per scope key, with a 5-minute soft TTL;
- on a stale hit it refreshes in the background without clearing the rendered list
  (stale-while-revalidate), so the rail never flashes back to a skeleton while the reader is switching;
- dedupes concurrent calls (article switch during an in-flight request reuses the same promise);
- exposes `loadMoreRail()` backed by `usePosts.loadMore`.

No backend change is required.

### 4. Collapse: two spines, one mechanism

Both panels collapse to a 2rem 竖排书脊 at their own edge, using `writing-mode: vertical-rl`, with a
`border-right` (rail) / `border-left` (TOC) hairline standing in for the expanded panel's `border-top`:

- Rail spine: an outward chevron + 文章清单 + the total count, hugging the left edge.
- TOC spine: an outward chevron + 目录 + the active section number, hugging the right edge, so
  "where am I in this article" survives collapsing.

Both affordances are drawn the same way so the two panels read as a matched pair:

- expanded: a 1.55rem circular hairline button holding a small chevron
  (`<svg viewBox="0 0 24 24">` with `fill: none; stroke: currentColor`), pointing in the collapse
  direction (left for the rail, right for the TOC; the TOC/rail SVGs are mirrored with
  `transform: rotate(180deg)`), `title` for the tooltip, and `:hover` filling it with the accent colour.
  A text button ("收起") was tried first and read as body copy competing with the panel label in a
  200px column.
- collapsed: the spine carries the same chevron rotated to open outward, plus the vertical label and
  the count. Hover tints the spine with `rgba(139, 37, 0, 0.05)` and switches the stroke to accent.
- the spine geometry is fixed at `min-height: 11rem` so both collapsed states leave the bottom-right
  corner free for the desktop pet.

One head rule serves both panels (`.article-toc__head, .article-rail__head`), with a hairline
`border-bottom` under the label row and the display-serif count in accent red. The directory's
"阅读时，目录会跟随当前章节。" caption was removed — the following behaviour is now visible from the
active row itself, and the caption only added a third text style to a 240px column.

State lives in `localStorage` (`zhizhi-article-rail-collapsed`, `zhizhi-article-toc-collapsed`) through
a shared `usePersistedCollapse` composable; the value is applied during setup so there is no
expand-then-collapse flash. The TOC toggle is desktop-only (≥1281px) — the ≤1280px horizontal strip
keeps its current form, and `useTableOfContents.getReadingLine()` reads `.article-toc` only in that
branch, so nothing there is affected.

### 5. Rendering gates and reveal timing

- `useMediaQuery("(min-width: 1360px)")` gates both rendering and fetching, so phones never request the
  extra list. CSS gates layout independently (see 1).
- The rail's list arrives *after* `PostView` has already called `refreshReveal()`. Newly inserted
  `.rv` elements are invisible until the observer sees them, so the rail would silently stay hidden.
  `PostView` must call `refreshReveal()` again once the rail data renders — the same treatment the
  existing `retryPost` path uses.
- The rail container carries `.rv` + `data-reveal-delay="100"`, matching the TOC.
- The rail's rows are `<a>` and its toggles/spines are `<button>`, so `CursorEffects` already treats
  them as interactive through its `"a"` / `"button"` selectors. No change needed there.

## Component and File Scope

New files:

- `frontend/src/components/post/PostRail.vue` — rail markup: year-grouped rows, current marker, spine,
  toggle, 加载更多, 完整目录 link, active-row alignment.
- `frontend/src/composables/usePostRail.js` — scope resolution, singleton cache, stale-while-revalidate,
  pagination state.
- `frontend/src/composables/usePanelPin.js` — computes `--panel-shift` / `--panel-avail` / `is-parked`
  for both side panels on scroll and resize.
- `frontend/src/composables/useMediaQuery.js` — reactive `matchMedia` wrapper.
- `frontend/src/composables/usePersistedCollapse.js` — persisted collapse state shared by both panels.
- `frontend/src/lib/postGroups.js` — `groupByYear(posts)`.

Modified files:

- `frontend/src/views/PostView.vue` — render `PostRail`, wire the `--no-rail` modifier, call
  `ensureRail` / `loadMoreRail`, refresh reveal when the rail data lands.
- `frontend/src/components/post/PostToc.vue` — collapse toggle + spine; keep the existing active-entry
  alignment.
- `frontend/src/styles/post.css` — rail tokens and areas on `.post-reading-layout`, `.article-rail`
  rules, spine rules, the ≥1360px block, the desktop-only TOC toggle.
- `frontend/src/views/PostsView.vue` — use the shared `groupByYear`.
- `backend/tests/test_backend.py` — static CSS-contract tests (house style, see Validation).

## Edge Cases

- Article without `h2`/`h3`: no TOC; the rail still renders and `--no-toc` keeps its area.
- 栏目 with ≤2 published posts: rail falls back to the site-wide latest list; ≤2 posts site-wide: no rail.
- Current article outside the first 30 rows of its 栏目: pinned 当前篇 row, no position readout.
- Article whose 栏目 is empty/unknown: treated as the fallback case.
- Rail fetch fails or times out: the rail is not rendered; the article, TOC, prev/next and related posts
  all behave exactly as today. A rail failure must never surface an error state over the reading page.
- Viewport narrower than 1360px: no rail, no rail request; `--no-rail` keeps the article centered.
- Resizing across 1360px: the rail appears/disappears without moving the article column or the scroll
  position, because it only occupies space the article never used.
- Collapsed panel + reload: state is restored before first paint.
- Reduced motion: panel collapse/spine transitions are suppressed; nothing depends on animation.
- Sticky rail with a long list: the rail scrolls internally and never exceeds
  `calc(100vh - 8.5rem)`; the left margin keeps the spine off the viewport edge.

## Validation

### Automated checks

- `cd frontend && npm run build`
- `backend/.venv/Scripts/python.exe -m pytest backend/tests -q -p no:cacheprovider --basetemp=.tmp/pytest`
- `git diff --check`

New static contract tests in `backend/tests/test_backend.py`, in the style of
`test_toc_scroll_offset_variables_are_in_scope`:

1. `--post-rail-width` / `--post-rail-gap` are declared on `.post-reading-layout` and *not* on
   `.article-rail`, and all four `grid-template-areas` combinations exist. (A panel cannot read a
   sibling's custom properties; the same failure mode is already documented for the TOC.)
2. The rail cannot reach the reading column: `.article-rail` width is bounded by
   `min(var(--post-rail-width), calc(100% - var(--post-rail-gap)))`, the panel is `justify-self: start`
   while the TOC is `justify-self: end`, and `grid-template-columns` still contains no `auto` track
   (the invariant that keeps the article centered and toggle-independent).
3. The rail is not laid out below its breakpoint: `display: none` in the base rule and
   `@media (min-width: 1360px)` enabling it, so it can never be auto-placed into the ≤1280px stacked
   area template.
4. The rail's height is decoupled from the reading row: `.article-rail` is `height: 0` with no
   `max-height`, both panels inside it are `position: absolute`, and the panel's own cap is
   `calc(100vh - 8.5rem)` — i.e. the list may not be re-capped by the article body, and the rail must
   not receive a body element.

### Real-browser checks

Temporary database and a long article with ≥8 headings; never write to `storage/blog.db`.
Launch with `.\scripts\dev.ps1`.

At 1920×1080 and 1440×900:

- record the article body's `getBoundingClientRect()` left/top, then collapse the rail, collapse the
  TOC, and expand both — the recorded rectangle must be identical each time, and `window.scrollY`
  must not change;
- verify the rail shows the current 栏目's 编年索引 with the current row marked and scrolled into view;
- switch articles from the rail three times and confirm the rail list does not flash a skeleton;
- reload with both panels collapsed and confirm they restore collapsed before first paint;
- confirm 完整目录 lands on `/posts?category=…` and 加载更多 only appears when the server says `has_more`.

At 1366×768: rail and article must not touch; the rail must stay inside its track.

At 1280×800 and 390×844: no rail, no `GET /api/posts?category=` request, layout identical to today;
the horizontal TOC strip is unchanged and has no collapse toggle.

Console must be free of new errors or Vue warnings.

## Acceptance Criteria

- The left rail shows the current 栏目 in the site's 编年索引 form, with the current article locatable
  and marked.
- Both panels collapse to an edge spine and the choice survives reload and article switches.
- Collapsing or expanding any panel leaves the article column's position, width, and the scroll
  position unchanged.
- No rail, no rail request, and no layout change below 1440px.
- The rail cannot overlap the reading column at any width at or above its breakpoint.
- A rail fetch failure degrades to today's page silently.
- Frontend build, backend tests, and real-browser verification pass.

## Implementation Notes (2026-10-15)

Verified against the temporary fixture database
`output/playwright/article-rail-test.db` (12 工程 / 38 教学 / 3 算法 / 2 随想 posts). The fixture
generators are `output/playwright/create_article_rail_fixture.py` and
`extend_article_rail_fixture.py` (`output/` is git-ignored); `storage/blog.db` was never opened.

Measured at 1920×1080 on a 38-row 栏目 with a single-paragraph article, in every toggle state:

| state | rail panel | TOC | article body | document height | scrollY |
| --- | --- | --- | --- | --- | --- |
| both expanded | 14 → 326, 312×944 | 1656 → 1896 (240) | **575 / 760** | 1201 | 900 |
| rail collapsed | 14 → 46, 32×176 | 1656 → 1896 | **575 / 760** | 1201 | 900 |
| TOC collapsed | 14 → 326, 312×944 | 1864 → 1896 (32) | **575 / 760** | 1201 | 900 |

The rail's right edge (326) never reaches the article's left edge (575); the document height is
identical in every state, so no state change can clamp the scroll position — including on a
single-paragraph article, which the earlier body-derived cap could not achieve.

Other confirmed behaviours:

- one `/api/posts?category=…&page=1&limit=30` request per scope; switching articles and resizing
  1920 → 1500 → 1440 → 1400 renders or hides the rail with **no** further list request;
- 栏目 below three published posts falls back to the site-wide latest list (`随想` → head 最新, 17 rows,
  footer link `/posts`); exactly three posts keeps the category (`算法` → head 算法3/3);
- the rail shows 21 rows at 1920×1080 and 17 at 1440×900 (a fixed 217px cap showed three), and the
  current row is aligned into that area on mount, on article switch, and after a viewport resize
  (`navScrollTop` 351 / 534 respectively);
- the rail appears at 1440 and above and is absent from the DOM at 1400;
- 加载更多 appears only when the server reports `has_more` (30 of 38 rows) and grows the list to 38
  without changing the document height;
- collapsed spines render as 2rem vertical plates carrying a chevron, 文章清单 + count on the left and
  目录 + the active section number on the right; the rail/TOC restore collapsed on first paint after a
  reload;
- the directory's caption paragraph is gone from the DOM; toggles render as circular hairline buttons
  containing the chevron SVG;
- 1280px and 390px viewports render no rail and keep the single-column `"toc" "article"` template with
  the horizontal TOC strip at its sticky offset and no collapse toggle;
- no console errors or Vue warnings.

`test_backend.py` now holds 191 passing tests (four added above); `npm run build` and
`git diff --check` are clean.

### Corrections to the design above

- `CursorEffects.vue` was left unchanged. Its `INTERACTIVE_SELECTOR` already starts with `"a"` and
  `"button"`, and the rail's rows are anchors while its toggles and spines are buttons, so adding rail
  selectors would have been dead code.
- `usePostRail` does not expose loading/error refs: nothing consumes them, a failed rail fetch simply
  leaves the rendered list in place and the component unmounted.

## Revision after visual review (2026-10-15)

Review feedback: the directory caption was unnecessary, the rail was too narrow to be pleasant or
convenient, and neither collapse control looked good. All three were fixed by changing the design, not
the styling alone:

1. `.article-toc > p` ("阅读时，目录会跟随当前章节。") was deleted along with its CSS in both the desktop
   and the ≤1280px blocks. The behaviour is visible from the active row; the caption only added a third
   text style to a narrow column.
2. The rail was widened from 17rem to 19.5rem (`--post-rail-width`), the TOC from 220px to 15rem, and
   the rail's breakpoint raised from 1360px to 1440px so the panel is never squeezed by the `min()`
   bound at the width where it is shown. The gap token was tightened to
   `clamp(1.25rem, 2vw, 2.25rem)` so the full 312px fits at 1440px.
3. Row typography was reworked: titles moved from the inherited 0.62rem monospace to the 0.72rem
   display serif used by the `/posts` index, dates to a 0.56rem mono caption, row padding to
   `0.55rem 0.5rem 0.55rem 0.75rem`, plus a hairline separator between adjacent rows and an accent
   left border with a faint tint for the current row.
4. The height cap was replaced by the decoupling described in section 1. The body-derived cap
   (`useRailHeight.js`, now deleted) solved document inflation but left the list showing ~3 rows; a
   zero-height sticky box with an absolutely positioned panel gives the list the whole available
   viewport (21 rows at 1080p with the 38-row fixture) while keeping the document height independent
   of the rail.
5. Both collapse controls were redesigned (see section 4): circular hairline chevron buttons when
   expanded, chevron + vertical label + count spines when collapsed, with hover states.
6. The rail's active-row alignment now also re-runs on window resize, mirroring `PostToc`. Without it,
   shrinking the viewport left the current row below the rail's visible area (measured at 1440×900).
7. The `matchMedia` gate in `PostView` was moved to 1440px to match the CSS breakpoint; left at 1360 it
   rendered and fetched the rail in the 1360–1440 band where CSS hides it.

The unit-test contract changed accordingly: `test_side_panels_are_pinned_by_script_not_by_sticky`
locks in that neither base panel rule may use `position: sticky`, that they read `--panel-shift` /
`--panel-avail`, and that the rail's `pointer-events: none` is paired with `pointer-events: auto` on
the panels themselves;
`test_article_rail_height_is_decoupled_from_the_reading_row` asserts the zero-height outer box, the
absolutely positioned panels and the viewport-only cap, and that `PostView` does not pass a body
element.

## Revision after layout review (2026-10-15, second round)

Follow-up defects reported from real use, both traced to the same root cause and measured at 1920×700
with a 217px article:

1. **"The left column is longer than the page."** Because the panel is anchored to the top of its grid
   area, before the area reached the sticky offset the panel's bottom extended past the fold — the
   完整目录 footer was clipped at the viewport edge (panel 155 → 794 in a 780px window).
2. **"Once collapsed, it won't open."** Sticky clamps the panel to its grid area; on a short article
   the area passes in ~200px of scrolling, so the panel slid from 109 up to **-193**. The collapse
   button's centre then resolved to `DIV.print-nav__inner` (the fixed site header) at 700px height,
   and on the right the TOC's toggle was at y=-63 — entirely off-screen.

Fixes:

- both panels are now `position: absolute` grid children whose containing block is their own grid area,
  with `--panel-shift` / `--panel-avail` / `is-parked` supplied by `usePanelPin.js` (scroll + resize
  driven, no `position: sticky` anywhere in the base rules);
- the panel's height is `min(viewport room, room before the area ends)`, so it is never clipped by the
  fold and never spills past the reading area;
- the entrance animation is a self-filling keyframe (`side-panel-in`) instead of `.rv`: a zero-height
  box's intersection result is not worth betting on, and a missing `.vis` made the whole panel invisible
  *and* unclickable;
- `.article-rail` carries `pointer-events: none` (its zero-height box must not shadow the article
  column) and the panels write `pointer-events: auto` back — `pointer-events` is inherited, so without
  it every control in the panel hit-tested through to the grid container ("visible but dead").

Also fixed in this round: `.article-toc button` (the directory row rule) was also styling the toggle
and the spine, which made the toggle `width: 100%` — a 240×25 box crossing the viewport's right edge
(1721 → 1961 at 1920) instead of a 25px round button. Row rules are now scoped to `.article-toc nav button`.

Verified after the fix: at 1920×1080 and 1920×640, scroll positions 900/4000 and 900 respectively, both
toggles and both spines hit-test to themselves and real mouse clicks collapse and expand them; the
article body stays at left 575 (1920) / 335 (1440) throughout; on the short article the panels track the
area (412 → 212), pin at 108, shrink as the area ends and park; 1280/390 keep the untouched
single-column layout with the sticky horizontal TOC strip.

`backend/tests/test_backend.py` holds 192 passing tests.

## Revision after frame-crossing review (2026-10-15, third round)

Three issues reported from real use, all reproduced and measured before changing anything.

### 1 & 2. Two navigations looked like full page reloads

`App.vue` keyed the router view by `viewRoute.fullPath`. Any query-only navigation therefore
changed the key and remounted the whole view:

- On `/posts`, `加载更多` appends page 2, then `scheduleRouteSync` writes `?page=2` back to the URL.
  The remount re-rendered the skeleton (which reads as "the page refreshed") and `onMounted`
  refetched page 1 before the appending list reappeared.
- From an article, the rail's 完整目录 link used `?category=`, but `PostsView` only reads `q` / `cat` /
  `page`, so the filter was dropped, the URL was normalised to `/posts` and the view remounted a
  second time.

Fixes: the key is now `viewRoute.path` (a query change updates the mounted view in place, which
`PostsView` already supports via its `route.query` watcher), and the link is `?cat=`.

Measured after the fix: on `/posts?cat=教学`, one click on 加载更多 produced exactly **one** request
(`/api/posts?category=教学&sort=latest&limit=10&page=2`), the row count went 10 → 20, the first row's
DOM node survived (`isConnected === true`) and no skeleton state appeared; from
`/posts/article-rail-long-read`, clicking 完整目录 landed on `/posts?cat=工程` with exactly **one**
request and the 工程 chip marked active.

### 3. The panels still crossed the page frame

The frame (`.print-page`) is `min(1180px, 100vw - 48px)`. At 1920 the frame is 1180 with 370px of
margin per side, so everything fits; below 1884 the frame stays 1180 while the margins shrink, and the
panels — which are capped only by their own 1fr track — walk straight over the frame's border.
Measured against the previous rules (`!important` overrides reproducing them exactly), the panel's
overlap with the frame's box was:

| viewport | frame | rail (overlap) | TOC (overlap) |
|---|---|---|---|
| 1920 | 365–1545 (1180) | 14–326 (none) | 1656–1896 (none) |
| 1690 | 250–1430 (1180) | 12–324 (**74**) | 1428–1668 (**2**) |
| 1600 | 205–1385 (1180) | 11–323 (**118**) | 1339–1579 (**46**) |
| 1500 | 155–1335 (1180) | 10–322 (**167**) | 1240–1480 (**95**) |
| 1440 | 125–1305 (1180) | 9–321 (**196**) | 1181–1421 (**124**) |

This is exactly what the report's screenshot shows: on a 1920 screen nothing looks wrong, and the
narrower the window the further both panels march over the frame, worst on the left because the rail is
the wider of the two.

There is no arrangement at those widths that keeps a 1180px frame, a 760px reading column, a 312px
rail and a 240px TOC apart, so the frame itself now narrows:

```css
.print-post-view {
  --post-frame-width: min(1180px, max(800px, calc(100vw - 40rem)));
  --post-outer-margin: calc((100vw - var(--post-frame-width)) / 2);
}
@media (min-width: 1281px) {
  .print-post-view .print-page,
  .print-post-view .print-related-section { width: var(--post-frame-width); }
}
```

The tokens live on `.print-post-view` because the frame and the panels are two branches of the tree
and must read the same numbers. The 800px floor is reached at 1440 and keeps the full 760px reading
column inside the frame with 20px of paper on each side; at 1884px and above the frame is 1180 again,
so wide screens are byte-for-byte unchanged. `.print-related-section` narrows with it, otherwise the
two frames would disagree by 380px just below the article.

Each panel's width now takes a third `min()` term, the clearance from the frame:

```css
width: min(
  var(--post-rail-width),
  calc(100% - var(--post-rail-gap)),
  calc(var(--post-outer-margin) - var(--post-rail-margin) - var(--post-panel-breath))
);
```

`--post-rail-margin` / `--post-toc-margin` are the same variables that drive `margin-left` /
`margin-right`, so the edge inset and the width budget cannot drift apart. Measured after the fix
(article body 760px in every row, no overlap anywhere):

| viewport | frame | rail | TOC | clearance |
|---|---|---|---|---|
| 1920 | 365–1545 (1180) | 14–326 (312) | 1656–1896 (240) | +39 / +111 |
| 1884 | 347–1527 (1180) | 14–326 (312) | 1620–1860 (240) | +21 / +93 |
| 1700 | 315–1375 (1060) | 12–297 (285) | 1438–1678 (240) | +18 / +63 |
| 1690 | 315–1365 (1050) | 12–297 (285) | 1428–1668 (240) | +18 / +63 |
| 1600 | 315–1275 (960) | 11–297 (286) | 1339–1579 (240) | +18 / +64 |
| 1512 | 315–1187 (872) | 10–297 (287) | 1252–1492 (240) | +18 / +65 |
| 1440 | 315–1115 (800) | 9–297 (288) | 1181–1421 (240) | +18 / +66 |
| 1320 | 255–1055 (800) | hidden | 1073–1302 (229) | — / +18 |
| 1281 | 236–1036 (800) | hidden | 1053–1264 (210) | — / +17 |

Below 1440 the rail is not laid out at all, so only the TOC needs the clearance and it thins from 240
to 210 by 1281; below 1281 the TOC returns to its horizontal sticky strip and the frame goes back to
`min(1180px, 100vw - 48px)`.

### 4. The collapse chevrons pointed the wrong way

The four controls do not share one path direction: the rail's toggle and spine and the TOC's spine use
the left-pointing `M15 5l-7 7 7 7`, the TOC's toggle uses the right-pointing `M9 5l7 7-7 7`. Round two
added `rotate(180deg)` to the TOC's toggle and spine, which flipped both of the ones that were already
correct — that is why the right-hand panel showed a left arrow where a right one was expected.

The required convention is: collapse points outward (rail → left, TOC → right), expand points inward
(rail → right, TOC → left). Only the rail's spine was wrong; it now carries the single 180° rotation
in `post.css` (verified from computed styles in all four states: rail toggle `none` + left path, TOC
toggle `none` + right path, rail spine `matrix(-1,0,0,-1,0,0)`, TOC spine `none`).

### Test contract

`test_side_panels_cannot_reach_the_reading_column` was extended to require the third `min()` term and
that each panel's edge inset comes from the same variable as its width budget;
`test_reading_frame_narrows_to_make_room_for_the_side_panels` is new and locks the frame tokens, the
`min-width: 1281px` scope, the `editorial.css` load order that makes the override effective, and the
per-panel width terms; `test_panel_chevrons_point_outward_when_collapsing` allows exactly one
`rotate(180deg)` in `post.css` and requires it to land on `.article-rail__spine svg`;
`test_router_view_survives_query_only_navigation` bars `fullPath` from the router view's key.

`backend/tests/test_backend.py` holds 195 passing tests. The article column invariant still holds
under every toggle combination at 1690×950: the body stays at left 460 / width 760 / top -527 while
both panels are collapsed, expanded, or mixed.

## Revision after scroll-smoothness review (2026-10-15, fourth round)

Reported symptom: both panels flicker/stutter while scrolling — they do not track the copy.

**Root cause (measured).** The panel is an absolutely positioned element inside the document, and
`usePanelPin.js` corrected its position with `top: var(--panel-shift)` on every `scroll` event. The
browser moves the panel as ordinary content first, then dispatches the scroll event, and only then does
the handler write the correction back. The write therefore always lands one frame after the paint:

| scrollY | layout top | panel top (measured) | pin line | `--panel-shift` |
|---|---|---|---|---|
| 5129 | −4018 | 54 | 108.8 | 4072px |
| 5184 | −4074 | 53 | 108.8 | 4127px |
| 5239 | −4129 | 53 | 108.8 | 4182px |

The panel sits at 53–54px instead of 108.8px and the error is exactly one frame's scroll delta, per
frame, without ever converging — at 55px/frame the panel was permanently 55px behind. Faster scrolling
made it worse, which is precisely the "flicker" in the report. Sampled over 14 frames the old build gave
`railTop` variants `[53, 54]`; the target is a single value.

**Fix: move the pinned state out of the scroll path.** The vertical lifecycle is now three segments,
and the scroll handler writes no coordinates at all:

1. *Before the pin line* — `top: 0` inside the grid area, so the panel simply sits at the reading
   area's top and scrolls with the copy, compositor-handled, no JS.
2. *Past the pin line* — `.article-toc.is-pinned` / `.article-rail.is-pinned` switch to
   `position: fixed; top: var(--panel-pin)`. Fixed elements do not participate in scrolling at all,
   so there is nothing to lag behind.
3. *Insufficient room* — `is-parked` hides the panel as before.

Both states place the panel at the same y at the crossing point (in flow its top *is* the area top, and
the switch happens when that equals the pin line), so the handover is seamless. Measured across the
crossing:

| scrollY | area top | panel top | state |
|---|---|---|---|
| 400 | 710 | 710 | flow |
| 900 | 210 | 210 | flow |
| 990 | 120 | 120 | flow |
| 1005 | 105 | 109 | pinned (fixed) |
| 1060 | 50 | 109 | pinned (fixed) |
| 6000 | −4890 | 109 | pinned (fixed) |

`--panel-shift` is gone from `post.css` and the composable, and the test suite now forbids it: any
return to a per-frame `top` reintroduces the one-frame lag. The handler only computes the area rect,
the available height and two booleans, and writes `--panel-avail` **only when the number changes** —
in the steady state a scroll frame produces no style writes whatsoever. `--panel-pin` (the pin line in
px, derived from the same `pinRem` the math uses) is written on mount and on resize, so CSS and JS
cannot drift apart.

Two consequences worth recording:

- `position: fixed` resolves `left`/`right` against the viewport rather than against the grid area,
  which moves each panel ~7px inward (half the scrollbar). Re-measured clearances at 1920 / 1690 /
  1600 / 1440 / 1320 / 1281 are +34/+13/+13/+13/—/— px on the left and +106/+58/+59/+61/+13/+12 px on
  the right, with the reading column still exactly 760px everywhere.
- The rule lives inside `@media (min-width: 1281px)` because `.article-toc.is-pinned` outweighs the
  narrow-screen `.article-toc`; left unscoped it would turn the ≤1280px horizontal TOC strip into a
  fixed panel. Verified at 1200 and 390: `position: sticky`, `top: 56.8px`, flex strip intact.

Re-verified after the fix: 14 frames of 55px/frame scrolling give a single `railTop` value (109) and a
single `--panel-avail` value (963px); the TOC's inner nav does not scroll during article scrolling
(`navScrollTop` stayed 0 over 40 frames), so its smooth active-item alignment is not a second source of
jitter; on a short article (6576px document) the panel goes flow → pinned → parked with the toggle
always hit-testable.

`backend/tests/test_backend.py` holds 195 passing tests; the pin test was renamed to
`test_side_panels_are_pinned_without_touching_the_scroll_path` and now asserts `position: fixed` for the
pinned state, that `--panel-shift` exists nowhere, that `--panel-pin` is script-fed, that the rule is
scoped to ≥1281px while the narrow strip keeps `position: sticky`, and that `--panel-avail` is only
written when it changes.

## Follow-up fix while starting the dev servers (2026-10-15, fifth round)

While bringing the environment up, one `P0` item from the triage list was fixed because it was a
straight defect: the tag chips in the article hero linked to `/posts?tag=…`, a parameter the
directory page never reads.

Reproduced: clicking `链表` on the article page produced URL `/posts`, all 2 posts listed and the
`全部` chip highlighted — the filter was silently dropped and `scheduleRouteSync` then normalised the
URL, so the click did nothing at all.

Options considered:

- Add `tag` as a fourth facet to `PostsView` (`routeQueryKey` / `buildRouteQuery` / `listParams` /
  `applyRouteState`) plus a chip in the toolbox. Implemented, verified working, then **reverted**:
  `test_posts_page_is_a_single_year_grouped_index` explicitly asserts `"selectedTag" not in view` and
  the contract tests ban `tag-filter-button` / `article-tag-filter` selectors. The project's rule
  (`AGENTS.md`) is that tags are display-and-search only and that 栏目 is the front end's *only*
  filter facet, precisely so the filter bar cannot regress into a second tag cloud.
- **Chosen:** send tag clicks into the search dimension — `{ path: "/posts", query: { q: tag } }`.
  The tag text is almost always present in the post's own tag (and often in its title/body), so the
  result set is right, no new facet is introduced, and the existing search box shows the active term
  with its own clear button.

Measured after the fix: article hero chip → `/posts?q=链表`, exactly **one** request
(`/api/posts?q=链表&sort=latest&limit=10&page=1`), the search box filled with `链表`, meta line
`搜索结果 · 2 篇`, and the 清除筛选 button visible. A search that matches nothing
(`?q=不存在的标签`) shows `搜索结果 · 0 篇` with the empty state, and `?cat=教学&q=链表` keeps both
dimensions (1 post, 教学 chip active).

A latent duplicate request surfaced on the way: `watch(normalizedQuery)` calls `scheduleReload()`,
which forces a fetch and therefore bypasses the `lastFetchedKey` de-duplication, so landing on
`/posts?q=…` fetched the same page twice (verified: two identical requests). The watcher now skips the
row while `applyingRouteState` is true, mirroring the category watcher. Verified: one request on entry,
and typing in the box still triggers the debounced reload (`?q=第一题` → 1 post).

`backend/tests/test_backend.py` holds 196 passing tests;
`test_article_tag_chips_lead_to_a_search_that_actually_works` locks both halves of this fix.

Still open (unchanged, awaiting a product decision): first-screen visibility of the panels, the
`最新` fallback scope, the short-article near-invisibility of the rail, the 1281–1884px frame trade-off,
the bare-array branch of `/api/posts?limit=N`, and the chip row only listing non-empty categories.
