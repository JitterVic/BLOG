# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A Chinese-language personal blog: **Vue 3 SPA frontend + Flask backend + SQLite**, with a single-admin server-rendered admin panel. UI copy, commit messages, and flash messages are in Chinese — match that when editing user-facing strings.

There is also an `AGENTS.md` with coding-style conventions (4-space Python, `<script setup>` + 2-space Vue, PascalCase components, camelCase JS); read it before large style-sensitive changes.

## Commands

```bash
# Backend
python -m pip install -r requirements.txt
python backend/app.py            # serves API + admin on 127.0.0.1:5000, auto-loads root .env

# Frontend (run from frontend/)
cd frontend
npm install
npm run dev                      # Vite dev server on 127.0.0.1:5173, proxies /api + /uploads to :5000
npm run build                    # builds frontend/dist/ — REQUIRED for Flask to serve the SPA
npm run preview
```

`.\一键启动.ps1` (Windows/PowerShell) boots both servers detached, health-checks them, and writes logs/PIDs to `.run/`.

### Test suite

`backend/tests/test_backend.py` — ~53 pytest tests covering API contracts, security boundaries, upload validation, admin auth, and deploy-script encoding guards. Run with:

```bash
python -m pytest backend/tests -q -p no:cacheprovider --basetemp=<clean-dir>
```

The `--basetemp` flag is **required on this Windows dev machine** because `C:\Users\22937\AppData\Local\Temp\pytest-of-22937` has a corrupt ACL. The repo's `.pytest_cache/` is also ACL-broken — do not touch it. There is **no frontend test suite**.

## Runtime topology (important)

- **Dev = two servers.** Vite (`:5173`) serves the SPA and proxies `/api` and `/uploads` to Flask (`:5000`). Edit frontend → hot reload; no rebuild needed.
- **Prod = one server.** Flask serves everything: the built SPA from `frontend/dist/`, the `/api/*` JSON, `/uploads/*`, and the admin panel. Frontend changes require `npm run build` before Flask reflects them. If `dist/` is missing, the catch-all route returns a JSON "please build" message instead of the app.

## Backend architecture

The whole backend is three flat modules under `backend/` (no package — running `python backend/app.py` puts `backend/` on `sys.path`, so imports are top-level like `from store import ...`). For a WSGI server use `gunicorn --chdir backend app:app`.

- **`app.py`** — `create_app()` app factory; module-level `app = create_app()` is the WSGI entrypoint. Loads root `.env` at import time via `env_loader`. Defines all routes and thin request/response shaping (`summarize_post`, `build_profile_form`, `build_edit_post`). Delegates all persistence and rendering to `BlogStore`. Includes security audit logging (`audit()` helper) and login rate-limiting keyed by `BLOG_TRUSTED_PROXY_COUNT`.
- **`store.py`** — `BlogStore`, the single hub for persistence, Markdown rendering, sanitization, uploads, slugs, read-time, and excerpts. **Most logic lives here.**
- **`content.py`** — default seed data (`POSTS`, `SITE_CONFIG`), inserted only when the tables are empty.
- **`env_loader.py`** — minimal hand-rolled `.env` parser (no python-dotenv dependency); does not override already-set env vars.
- **`templates/`** — server-rendered admin pages (`admin_login.html`, `admin_dashboard.html`, `admin_write.html`, `admin_profile.html`, `admin_media.html`, `admin_base.html`). The admin UI is classic Flask+Jinja, NOT Vue.

### Routing model

Three route groups coexist in one Flask app, and their ordering/guards matter:
1. **Public JSON API** — `/api/health`, `/api/site`, `/api/posts`, `/api/posts/<slug>`. Public endpoints only ever expose `status = 'published'` rows. Also public: `/feed.xml` (Atom), `/sitemap.xml`, `/robots.txt`, `/uploads/<path>`.
2. **Admin** — registered under a **configurable prefix** (`BLOG_ADMIN_PREFIX`, default `/admin`). Routes are built with f-strings at app-creation time (`f"{admin_prefix}/login"`, etc.), gated by the `@admin_required` session check. Includes admin-only JSON helpers for Markdown preview/import, image upload, autosave, publish preflight validation, and revision list/preview/restore.
3. **SPA catch-all** — `/<path:path>` serves static files from `dist/` or falls back to `index.html`. It **explicitly 404s** anything under `api/`, `uploads/`, or the admin prefix so those groups aren't swallowed. Server-side og: meta injection happens only for `/posts/<slug>` in `render_spa_index()`. When changing the admin prefix or adding top-level routes, keep this guard in sync.

### Data model & persistence conventions

Three SQLite tables: `site_profile` (a single enforced row, `id = 1`), `posts`, and `post_revisions` (snapshots at key lifecycle points — manual save, publish, unpublish, restore; capped at 50 per post).

- **JSON-in-TEXT columns.** `social_links`, `about_intro`, `update_calendar`, `tags`, `sections` are stored as JSON strings and round-tripped through `JSON_FIELDS` in `_row_to_dict`. When reading rows, go through `BlogStore` helpers so these are decoded; don't hand-parse rows.
- **Markdown is the source of truth.** `html_content` is **re-rendered from `markdown_content` on every read** in `_row_to_dict`, so a stored `html_content` is effectively a cache. To change how posts render, change `render_markdown`, not stored HTML.
- **Schema migrations are ad-hoc.** `_create_schema` uses `CREATE TABLE IF NOT EXISTS`; `_migrate_schema` adds columns via guarded `ALTER TABLE ADD COLUMN` (checked against `PRAGMA table_info`). Add new columns the same way — there is no migration framework.
- **Post lifecycle:** `status` is `'draft'`, `'published'`, or `'trashed'`. Drafts are invisible to all public API/pages. Trashed posts are hidden from the dashboard list and public API, auto-purged after 30 days (`purge_expired_trash` runs on dashboard load and at startup). `save_post` takes an `action` (`draft`/`published`); slugs are auto-uniquified via `ensure_unique_slug`.

### Security boundary — HTML sanitization

All Markdown output passes through `sanitize_html` (`SafeHTMLCleaner`, an allowlist `HTMLParser`) before it is ever stored or returned. This is the app's main XSS boundary — treat it as security-sensitive:
- Tag/attribute allowlists (`ALLOWED_HTML_TAGS`, `ALLOWED_HTML_ATTRS`); `on*` handlers and disallowed tags are dropped, `script/style/iframe/...` have their content removed.
- Link `href` limited to `http`/`https`/`mailto`; image `src` limited to `http(s)` or in-app `/uploads/<allowlisted-folder>/...` paths (`_is_safe_image_url` → `is_allowed_public_upload_path`).
- Uploads are validated by extension, written under `storage/{avatars,media}/` with timestamped safe names, and served via `/uploads/<path>` only if `is_allowed_public_upload_path` passes. Changes here can open path-traversal / XSS holes — be deliberate.

## Frontend architecture

Vue 3 (`<script setup>`) + Vue Router 4 + Vite 6. No Pinia/Vuex.

- **Composables are the store.** `composables/use*.js` hold module-level `ref`s as singletons and dedupe in-flight requests (see `useSite.js`: cache in a module `ref`, share one pending promise). Import the composable to read/refresh shared state; don't refetch per-component.
- **`services/api.js`** — the only place that talks to the backend. `fetch` wrapper with timeout + `AbortController`, throwing typed `ApiError` (`.code`, `.status`). Base URL is `/api` (overridable via `VITE_API_ROOT`); relies on the Vite proxy in dev.
- **`views/`** are router pages (Home, Posts, Post, About, NotFound); **`components/`** are shared UI (SiteHeader, plus decorative FloatingCat / CursorEffects). Router uses `createWebHistory` (real paths, no hash), which is why the Flask catch-all must serve `index.html`.
- Shared styles in `src/styles.css` and `src/styles/editorial.css`; keep new CSS there unless tightly component-scoped.

## Configuration

Root `.env` is auto-loaded (see `.env.example`). Key vars: `BLOG_SECRET_KEY` (≥32 chars), `BLOG_ADMIN_PASSWORD` (≥12 chars), `BLOG_ADMIN_PREFIX`, `BLOG_DATABASE_PATH`, `BLOG_HOST`, `BLOG_PORT`, `BLOG_DEBUG`. Also read from env in code: `BLOG_COOKIE_SECURE`, `BLOG_MAX_UPLOAD_BYTES`, `BLOG_TRUSTED_PROXY_COUNT` (login rate-limit IP source: 0=remote_addr, N≥1=XFF倒数第N段), `BLOG_HSTS_MAX_AGE` (HSTS seconds, 0=off, only when COOKIE_SECURE=true). A relative `BLOG_DATABASE_PATH` resolves against the repo root, not the CWD.

`storage/` (SQLite DB + uploaded avatars/media) is gitignored — it is live runtime data. Back up `storage/blog.db`, `storage/avatars/`, `storage/media/` before schema changes or destructive operations.

## Ops / 部署

- **`deploy.sh`** — Linux 一键部署（preflight、venv、pytest、前端构建、systemd 硬化、Nginx + certbot TLS、健康探测）。以 `set -Eeuo pipefail` 运行，幂等可重跑。
- **`deploy/backup.sh`** — WAL 安全备份（`sqlite3.Connection.backup` + `PRAGMA integrity_check`），白名单拷贝 avatars/media，tar.gz 归档，保留 N 份。
- **`deploy/restore.sh`** — 从归档恢复（自动回滚点 + 完整性校验 + 删除残留 WAL/SHM + 健康探测）。
- **`deploy/blog.service.example`** — systemd 单元模板（含安全加固：NoNewPrivileges/ProtectSystem/ReadWritePaths 等）。
- **`一键验证.ps1`** — Windows 发布前验证（pytest + npm build + API 冒烟 + 可选 StrictLaunch 校验）。

`BLOG_TRUSTED_PROXY_COUNT` 语义：0（默认）= 完全忽略 `X-Forwarded-For`，直接用 `remote_addr`（直连部署安全默认值）；1 = 取 XFF 链最后一段（nginx `$proxy_add_x_forwarded_for` 追加模式下即真实客户端 IP）。部署到反代后端时改为 1，否则登录限流会把所有请求归入 127.0.0.1 桶。`deploy.sh` 在 `INSTALL_NGINX=1` 时会自动写入此值。
