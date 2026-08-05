# Repository Guidelines

## Project Structure & Module Organization

This repository is a Flask + Vue personal blog. Backend code lives in `backend/` as an installable Python package (`backend/src/blog/`): `app.py` defines routes and app startup, `store.py` handles SQLite persistence and Markdown rendering, `content.py` contains seeded/default content, and `src/blog/templates/` + `src/blog/static/` store the admin HTML pages and assets. `backend/pyproject.toml` declares dependencies (managed with uv). Frontend code lives in `frontend/src/`: `views/` contains route pages, `components/` shared UI, `composables/` reusable Vue state, `services/api.js` API calls, and `router/` route definitions. Linux deployment scripts live in `deploy/` (`deploy.sh`, systemd/Nginx examples, backup/restore); local dev scripts live in `scripts/` (`dev.ps1`, `verify.ps1`, `backup.ps1`). Runtime data and uploads are under `storage/`; do not commit private databases or uploaded media unless intentionally versioned. Build artifacts (`frontend/dist/`), local run logs (`output/`), and Playwright captures are generated files.

## Build, Test, and Development Commands

- `uv sync --directory backend --group dev --group prod` creates `backend/.venv` and installs Flask/Markdown/Pillow plus pytest and gunicorn.
- `backend/.venv/bin/python -m blog` starts the Flask API/admin server and loads `.env` from the repository root (Windows: `backend\.venv\Scripts\python.exe -m blog`).
- `cd frontend && npm install` installs Vue/Vite dependencies.
- `cd frontend && npm run dev` starts the Vite development server at `127.0.0.1:5173` with API proxying.
- `cd frontend && npm run build` builds production assets into `frontend/dist/`, which Flask can serve.
- `cd frontend && npm run preview` previews the built frontend locally.

## Coding Style & Naming Conventions

Use 4-space indentation for Python and keep functions small and route helpers explicit. Prefer `pathlib.Path` for filesystem paths and environment-backed configuration via `backend/src/blog/env_loader.py`. Vue files use `<script setup>`, 2-space indentation, PascalCase component files such as `PostCard.vue`, and camelCase JavaScript names. Keep shared CSS in `frontend/src/styles.css` unless a style is tightly coupled to a new component.

## Testing Guidelines

Backend tests live in `backend/tests/test_backend.py` and run with `backend/.venv/bin/python -m pytest backend/tests -q` (add `--basetemp=<clean-dir>` on Windows machines with broken temp-dir ACLs). Before submitting changes, run the backend test suite and execute `npm run build` to catch frontend compile errors. Frontend tests, if added, go next to components as `*.spec.js` and are documented in `package.json`.

## Commit & Pull Request Guidelines

Recent commits use concise, imperative summaries, for example `Refine single-page calendar flip navigation`. Keep subjects focused on one change. Pull requests should include a short description, manual verification steps, linked issues when available, and screenshots or Playwright captures for UI changes.

## Security & Configuration Tips

Never commit real `.env` secrets. Start from `.env.example`, change `BLOG_SECRET_KEY`, `BLOG_ADMIN_PASSWORD`, and `BLOG_ADMIN_PREFIX` before deployment, and keep `BLOG_DEBUG=false` in production. Back up `storage/blog.db`, `storage/avatars/`, and `storage/media/` before migrations or releases.
