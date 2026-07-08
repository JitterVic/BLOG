# Function-Preserving Project Optimization Design

Date: 2026-07-08
Project: Flask + Vue personal blog
Status: Approved design, pending implementation plan

## Summary

Optimize the project in small, reversible phases while preserving all existing user-visible behavior, API contracts, database structure, and deployment flow. The first optimization pass prioritizes frontend maintainability because the largest and lowest-risk cleanup target is `frontend/src/styles.css`; backend restructuring is deferred until after safer frontend cleanup and verification habits are established.

## Goals

- Improve maintainability without changing features or visual intent.
- Reduce risk by optimizing one bounded area at a time.
- Keep every phase independently verifiable.
- Avoid sweeping rewrites, dependency additions, API changes, database migrations, or redesigns.
- Preserve current homepage/about-page calendar panels, watermark behavior, floating cat behavior, article browsing, admin behavior, and backend responses.

## Non-Goals

- No visual redesign.
- No new product features.
- No API response shape changes.
- No route/path changes.
- No database schema changes.
- No deployment or dependency changes unless explicitly approved later.
- No large backend split before frontend cleanup and verification are stable.

## Current Context

The repository is a Flask + Vue blog application. Frontend code lives in `frontend/src`; backend code lives in `backend`. Current notable large files are:

- `frontend/src/styles.css`, approximately 68 KB.
- `frontend/src/components/CursorEffects.vue`, approximately 11 KB.
- `backend/store.py`, `backend/app.py`, and `backend/templates/admin_dashboard.html`.

The working tree already contains uncommitted changes from recent homepage/about-page/calendar/cat/backend work. Optimization must not overwrite or discard those changes.

## Recommended Approach

Use a phased, frontend-first optimization sequence:

1. CSS maintainability cleanup.
2. Cursor effects component cleanup.
3. Calendar panel and floating cat boundary cleanup.
4. Frontend API/composable cleanup.
5. Backend readability cleanup.

This approach is preferred because it starts with the largest low-risk maintainability target, keeps behavior stable, and delays higher-risk backend changes until verification is stronger.

## Phase 1: CSS Maintainability Cleanup

Objective: make `frontend/src/styles.css` easier to maintain without changing rendered behavior.

Allowed changes:

- Reorganize CSS into clearer sections such as global tokens, shell layout, article surfaces, calendar panels, floating cat, responsive rules, and reduced-motion rules.
- Remove exact duplicate or dead historical rules when verified safe.
- Consolidate repeated colors, spacing, shadows, and transitions into existing or new CSS variables when this does not alter appearance.
- Keep existing class names and component markup stable unless a small local rename is required and fully updated.

Not allowed:

- Redesigning page appearance.
- Changing responsive breakpoints for product reasons.
- Replacing the styling architecture with CSS modules, Sass, Tailwind, or another system.

Verification:

- `git diff --check`
- `cd frontend && npm run build`
- Browser check of homepage, about page, posts list, post detail, tags/archive surfaces, and floating cat.

## Phase 2: CursorEffects.vue Cleanup

Objective: keep the pointer visual effect the same while making the component safer and easier to reason about.

Allowed changes:

- Clarify internal helper functions.
- Ensure event listeners, animation frames, timers, and DOM references are cleaned up correctly.
- Reduce duplicated calculations.
- Keep external usage unchanged; `App.vue` should continue rendering `<CursorEffects />` the same way.

Not allowed:

- Changing the visible cursor effect style or interaction model.
- Adding configuration props unless explicitly needed by a later requirement.

Verification:

- `cd frontend && npm run build`
- Browser check that pointer effects still appear and page navigation does not produce console errors.

## Phase 3: Calendar Panels and Floating Cat Boundary Cleanup

Objective: preserve the current homepage/about-page panel behavior while clarifying boundaries between the composable, event constants, and floating cat.

Allowed changes:

- Improve names or comments inside `useCalendarPanels.js` if they reduce ambiguity.
- Keep `GO_TOP_EVENT` centralized and clearly used.
- Keep floating cat click, jump, hover, and reset behavior unchanged.
- Keep homepage/about-page panel order and controls unchanged.

Not allowed:

- Reworking the flip interaction.
- Changing panel names, routes, or visible copy.
- Changing the hidden-scrollbar-but-scrollable behavior.

Verification:

- Homepage cover/latest/hot switching works.
- About cover/story/contact switching works.
- Floating cat returns the relevant calendar page to its first panel/top behavior.
- `cd frontend && npm run build`

## Phase 4: Frontend API and Composable Cleanup

Objective: make frontend data access clearer without changing requests or responses.

Allowed changes:

- Small naming and structure improvements in `frontend/src/services/api.js` and `frontend/src/composables/useSite.js`.
- Centralize repeated API path or error handling code if behavior remains the same.

Not allowed:

- Changing API URLs.
- Changing return shapes.
- Changing loading/error UI behavior.

Verification:

- Homepage latest/hot posts load.
- Posts list loads.
- Post detail loads.
- About/site information loads.
- `cd frontend && npm run build`

## Phase 5: Backend Small-Step Cleanup

Objective: improve readability of backend code without changing contracts.

Allowed changes:

- Extract small route helpers in `backend/app.py` where this reduces duplication.
- Clarify local helper names in `backend/store.py`.
- Remove obvious duplication while preserving SQL behavior and Markdown rendering output.
- Keep admin template behavior stable.

Not allowed:

- Database migrations.
- API route changes.
- JSON shape changes.
- Authentication/session behavior changes.
- Upload policy changes.

Verification:

- `python -m py_compile backend/app.py backend/store.py`
- Backend health endpoint smoke test.
- Posts list/detail/site API smoke tests.
- Frontend build still passes.

## Cross-Phase Safety Rules

- Work in one phase at a time.
- Keep diffs small and reviewable.
- Run verification before declaring a phase complete.
- If a phase reveals behavior ambiguity, stop and ask before changing behavior.
- Do not discard or overwrite existing uncommitted work.
- Do not introduce new dependencies without explicit approval.

## Success Criteria

The optimization effort is successful when each completed phase:

- Preserves existing functionality.
- Builds successfully.
- Has a clear before/after rationale.
- Reduces complexity, duplication, or maintenance risk.
- Leaves the repository in a state where work can stop safely before the next phase.

## Implementation Planning Entry Point

The first implementation plan should cover Phase 1 only: CSS maintainability cleanup. Later phases should each receive their own implementation plan after Phase 1 is verified.
