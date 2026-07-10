# Repository Guidelines

## Project Structure & Module Organization

This repository is a Flask + Vue personal blog. Backend code lives in `backend/`: `app.py` defines routes and app startup, `store.py` handles SQLite persistence and Markdown rendering, `content.py` contains seeded/default content, and `templates/` stores the admin HTML pages. Frontend code lives in `frontend/src/`: `views/` contains route pages, `components/` shared UI, `composables/` reusable Vue state, `services/api.js` API calls, and `router/` route definitions. Runtime data and uploads are under `storage/`; do not commit private databases or uploaded media unless intentionally versioned. Build artifacts (`frontend/dist/`), local run logs (`output/`), and Playwright captures are generated files.

## Build, Test, and Development Commands

- `python -m pip install -r requirements.txt` installs Flask and Markdown dependencies.
- `python backend/app.py` starts the Flask API/admin server and loads `.env` from the repository root.
- `cd frontend && npm install` installs Vue/Vite dependencies.
- `cd frontend && npm run dev` starts the Vite development server at `127.0.0.1:5173` with API proxying.
- `cd frontend && npm run build` builds production assets into `frontend/dist/`, which Flask can serve.
- `cd frontend && npm run preview` previews the built frontend locally.

## Coding Style & Naming Conventions

Use 4-space indentation for Python and keep functions small and route helpers explicit. Prefer `pathlib.Path` for filesystem paths and environment-backed configuration via `backend/env_loader.py`. Vue files use `<script setup>`, 2-space indentation, PascalCase component files such as `PostCard.vue`, and camelCase JavaScript names. Keep shared CSS in `frontend/src/styles.css` unless a style is tightly coupled to a new component.

## Testing Guidelines

No automated test suite is currently configured. Before submitting changes, run the backend locally and execute `npm run build` to catch frontend compile errors. For future tests, place backend tests under `backend/tests/` or `tests/` using `test_*.py`, and frontend tests next to components as `*.spec.js`; document any new runner in `package.json` or `requirements.txt`.

## Commit & Pull Request Guidelines

Recent commits use concise, imperative summaries, for example `Refine single-page calendar flip navigation`. Keep subjects focused on one change. Pull requests should include a short description, manual verification steps, linked issues when available, and screenshots or Playwright captures for UI changes.

## Security & Configuration Tips

Never commit real `.env` secrets. Start from `.env.example`, change `BLOG_SECRET_KEY`, `BLOG_ADMIN_PASSWORD`, and `BLOG_ADMIN_PREFIX` before deployment, and keep `BLOG_DEBUG=false` in production. Back up `storage/blog.db`, `storage/avatars/`, and `storage/media/` before migrations or releases.
