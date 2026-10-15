# CLAUDE.md

This file provides architectural context and operational constraints for AI assistants working in this codebase.

## 1. Overview & Runtime Topology

- **Stack**: Vue 3 SPA (Vite 6, `<script setup>`) + Flask 3 backend + SQLite (WAL mode).
- **Admin Panel**: Server-rendered Jinja2 templates + ES Modules (`backend/src/blog/templates/` & `static/`), independent of the Vue SPA — but *not* visually independent: `static/admin/css/theme.css` holds the same design tokens as `frontend/src/styles/base.css` (paper/ink/rules/fonts/focus ring) and is `@import`ed by `base.css` and `login.css`. Admin templates must load the same Google Fonts as the front-end, carry `noindex, nofollow`, and use `rgb(var(--paper-rgb) / a)` instead of hard-coded `rgba(...)` paper literals.
- **Language**: Chinese for all UI strings, flash messages, and user-facing notifications.

### Topology Modes
- **Development**: Two servers. Vite (`:5173`) serves SPA with hot-reload and proxies `/api` and `/uploads` to Flask (`:5000`).
- **Production**: Single server. Flask serves compiled SPA assets from `frontend/dist/`, dynamic JSON `/api/*`, `/uploads/*`, and the Jinja admin panel under `BLOG_ADMIN_PREFIX`.

---

## 2. Key Commands

```bash
# Backend (package `blog` under backend/src/, managed with uv)
uv sync --directory backend --group dev --group prod
backend/.venv/bin/python -m blog          # Linux/macOS
.\backend\.venv\Scripts\python.exe -m blog # Windows

# Frontend
cd frontend
npm install
npm run dev      # 127.0.0.1:5173 (proxies /api -> :5000)
npm run build    # Output to frontend/dist/ (required for Flask SPA hosting)
npm run preview

# Test Suite (Windows basetemp required due to temp-dir ACL restrictions)
backend/.venv/bin/python -m pytest backend/tests -q -p no:cacheprovider --basetemp=.tmp/pytest

# Windows Local Automation
.\scripts\dev.ps1                          # Starts both servers under a watchdog job object
.\scripts\verify.ps1 -StrictLaunch         # Full pre-flight audit: tests + build + smoke + config
.\scripts\backup.ps1                       # Local WAL backup snapshot
```

---

## 3. Backend Architecture (`backend/src/blog/`)

Standard Python src-layout package (`pyproject.toml` managed by uv/hatchling):

- **`app.py`**: App factory `create_app()`, WSGI entrypoint (`gunicorn blog.app:app`), security hooks, blueprint registration, SPA fallback route with Open Graph meta injection.
- **`config.py`**: Typed config loader (`AppConfig`), validates production readiness (fails on weak passwords/keys in prod).
- **`routes/`**: Blueprint controllers:
  - `public.py`: Public JSON endpoints (`/api/site`, `/api/posts`, `/api/posts/<slug>`, `/api/health`). `/api/posts` always answers with one envelope (`items` / `total` / `page` / `per_page` / `has_more`); a missing `page` means `page=1` (with a 50-item default limit), never a bare array.
  - `feed.py`: Dynamic XML feeds (`/feed.xml`, `/sitemap.xml`, `/robots.txt`).
  - `spa.py`: SPA catch-all and OG tag injection for social crawlers.
  - `admin_auth.py`, `admin_pages.py`, `admin_posts.py`, `admin_api.py`: Admin panel endpoints.
- **`services/`**: Core business domain logic:
  - `post_service.py`: Post lifecycle (draft/publish/trash), slug generation, auto-trash purging (30 days), revisions.
  - `media_service.py`: Media management, usage tracking, Pillow validation/compression.
  - `profile_service.py` & `dashboard_service.py`: Site metadata and dashboard statistics.
  - `import_service.py`: Frontmatter and document import parser.
- **`repository/`**: SQLite persistence layer (`database.py`, `posts.py`, `revisions.py`, `profile.py`, `media.py`).
- **`markdown_tools/`**: `renderer.py` (Markdown parsing + `SafeHTMLCleaner` XSS filter), `analysis.py` (reading time & word count), `frontmatter.py` (front-matter incl. `keywords`).
- **`seo.py`**: Atom feed / sitemap / robots.txt builders and SPA `<head>` injection (title, OG, canonical).
- **`security.py`** + **`login_throttle.py`**: Session auth, CSRF validation, audit logging, rate limiting (`BLOG_TRUSTED_PROXY_COUNT`). Failure counters live in SQLite because gunicorn runs multiple workers.
- **`taxonomy.py`**: The fixed category vocabulary (`CATEGORY_PRESETS`) that the directory page filters by.
- **`store.py`**: `BlogStore` facade — the composition root that wires repositories into services and re-exports legacy helpers.

### Taxonomy: three layers, deliberately

- **Category (`category`)**: the *only* facet the front-end filters by, restricted to `taxonomy.CATEGORY_PRESETS` (算法 / 工程 / 教学 / 项目 / 随想 / 读书). The admin renders a `<select>` and the publish pre-flight rejects values outside the list — free-text categories turn the filter bar into a second tag cloud.
- **Tags (`tags`)**: free vocabulary, displayed and searchable, never used for filtering.
- **Keywords (`keywords`)**: aliases / synonyms / English spellings. Searchable only, and deliberately absent from every public payload (list rows, site payload, post detail).

---

## 4. Frontend Architecture (`frontend/src/`)

- **State Management**: Singleton Composables (`composables/use*.js`) storing module-scoped reactive state (`ref`) and deduplicating in-flight network requests. No Pinia/Vuex.
- **API Client**: `services/api.js` over `services/http.js` (Fetch API with timeout and typed `ApiError`).
- **Components**:
  - `components/home/`: Editorial cover flip deck — `HomeCover`, `HomeFeature`, `HomeLatestRow`, `HomeHotLedger`, `HomePageRail`.
  - `components/post/`: Article reader enhancements (`PostHero`, `PostToc`, `PostSequenceNav`, `RelatedPostsGrid`, `ImageLightbox`). The desktop reading layout is a viewport-wide symmetric three-track grid (`.post-reading-layout`), so the article keeps the viewport center and its 760px width no matter what the side panels do. `PostRail.vue` fills the previously empty left track with a **switchable-scope** chronological index — 本栏目 / 全站最新 / other 栏目, the options tucked into a menu behind the single word in the rail header so the rail never becomes a second filter bar; the scope is reader state (kept across articles) while a thin 本栏目 degrades to 最新 by default, and picking 本栏目 explicitly bypasses that policy. Data comes from one `/api/posts?category=…` request cached module-wide by `composables/usePostRail.js`. Both panels collapse to a chevron-topped vertical spine that carries no number (the two spines' numbers meant unrelated things), and persist via `composables/usePersistedCollapse.js`. Panels exist only at ≥1440px, are absolutely positioned grid children (their box must not affect the row height), and read their height from `composables/usePanelPin.js`; before the pin line they sit at the top of their grid area and scroll with the copy, past it `.is-pinned` switches them to `position: fixed`. Neither `position: sticky` (a short article's grid area would drag the panel off-screen together with the collapse button) nor a per-frame `top` written from the scroll handler (a DOM write always lands one frame after the scroll, so the panel shudders — measured a steady 55px lag at 55px/frame) is acceptable; the composable only toggles a class and writes `--panel-avail` when the value actually changes. A panel is hidden outright when the room left is under 260px *and* its content does not fit, so a short article never shows a 100px fragment that vanishes on the next scroll. Panel width takes three `min()` terms — design width, track − gap, and frame margin − edge inset − breath — and the reading frame itself narrows to `min(1180px, max(800px, 100vw - 40rem))` at ≥1281px, publishing its margin as `--post-outer-margin`: a 1180px frame plus a 312px rail plus a 240px TOC only fits above 1888px, so below that the frame must yield or the panels cross its border. Collapse chevrons point outward and expand chevrons inward, so `post.css` may contain exactly one `rotate(180deg)` (the rail's spine).
  - `components/posts/`: Directory page — `ArchiveLedger.vue` (the single year-grouped index) + `PostsToolbox.vue` (category filter + search).
  - `components/pet/`: Interactive desktop pet mascot (`CatPet.vue`, `CatAvatar.vue`). Text-free by design: single click = scroll to top, press-and-hold (or `P` when focused) = pet, drag = reposition (persisted, clamped to viewport), right-click or `M` = toggle sound, typing = bongo reaction. No speech bubble / tooltip strings.
- **Styling**: `styles/editorial.css` aggregating 12 cascade-ordered modules based on CSS custom properties. Sub-page vertical rhythm (`/posts`, `/about`, article detail) is viewport-height fluid via `clamp(..., N svh, <original>)` so the footer lands inside the first screen; `footer.css` drives the sticky-colophon flex chain through `.print-shell:has(> .print-main > .print-subpage | .print-post-view)`.

---

## 5. Security & Persistence Boundaries

1. **XSS Defense**: Raw Markdown is the source of truth. Rendered HTML is dynamically sanitized via `SafeHTMLCleaner` allowlists (`ALLOWED_HTML_TAGS`, `ALLOWED_HTML_ATTRS`) on every read.
2. **Public Upload Boundary**: Files written to `storage/{avatars,media}/`. `/uploads/<path>` requests must strictly pass `is_allowed_public_upload_path`.
3. **Reverse Proxy Trust**: When deployed behind Nginx, set `BLOG_TRUSTED_PROXY_COUNT=1` so login rate limiting correctly reads the client IP from the tail of `X-Forwarded-For`.
4. **Data Isolation**: `storage/` contains runtime databases and media assets and is excluded from git. Always backup via `deploy/backup.sh` or `scripts/backup.ps1` before structural migrations.
