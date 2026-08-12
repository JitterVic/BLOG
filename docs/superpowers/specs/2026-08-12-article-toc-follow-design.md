# Article Table of Contents Follow Design

Date: 2026-08-12
Status: Approved approach, pending written-spec review

## Context

Long article navigation currently advertises that the table of contents follows the reader, but a real-browser test with an 8,313-character article and 28 `h2`/`h3` entries reproduced two failures:

1. On desktop, the entire table of contents scrolls out of the viewport instead of remaining sticky.
2. In a long table of contents, the active entry can move beyond the TOC container's visible area because the container itself never follows the active entry.

The desktop sticky failure is caused by `overflow-x: hidden` on both `html` and `body`. In Chromium this makes those elements scrolling ancestors and prevents the nested sticky sidebar from sticking to the viewport. Temporarily changing the horizontal clipping to `overflow-x: clip` restored the TOC at its configured sticky offset.

The current active-section calculation also depends on headings intersecting a narrow `IntersectionObserver` band. This is fragile for long sections, rapid scrolling, restored scroll positions, reverse scrolling, and the end of the article.

## Goals

- Keep the desktop TOC visible beside the article while the article body is being read.
- Keep the mobile horizontal TOC attached below the site header while reading.
- Select the section that matches the reader's actual position in the article.
- Keep the active TOC entry visible inside the TOC's own scroll area.
- Preserve smooth heading navigation and reduced-motion behavior.
- Avoid changing article content, the database schema, or the real blog database.

## Non-goals

- Redesigning the visual language of article pages.
- Adding new heading levels beyond the current `h2` and `h3` navigation contract.
- Persisting reading position between separate browser sessions.
- Adding a frontend testing framework solely for this fix.

## Selected Approach

### 1. Restore sticky positioning

Replace root-level horizontal clipping based on `overflow-x: hidden` with `overflow-x: clip`. This still prevents decorative horizontal overflow from producing a scrollbar, but does not create the scrolling ancestor that breaks the article TOC's sticky positioning.

Desktop behavior remains a left sidebar with:

- `position: sticky` below the fixed site header;
- a viewport-bounded maximum height;
- independent vertical scrolling when the TOC is longer than the available space.

At widths up to 920px, the TOC becomes a horizontal sticky strip below the mobile site header instead of a normal in-flow block. It receives an opaque paper background, border treatment, and a suitable stacking level so article text does not show through it.

### 2. Derive the active section from the reading position

Replace the narrow-band heading observer with a scroll-position calculation scheduled through `requestAnimationFrame`.

The composable will retain the scanned heading elements and, on initial build, window scroll, and window resize:

1. Calculate a reading line below the fixed header/TOC area.
2. Select the last heading whose document position has crossed that reading line.
3. Keep the first heading active before the first section has crossed the line.
4. Force the final heading active when the document is at the bottom tolerance.

This calculation handles downward scrolling, reverse scrolling, large scroll jumps, initial restoration of a previous scroll position, and long content gaps without requiring invisible sentinel elements.

Scroll and resize handlers will be passive where applicable and coalesced into one calculation per animation frame. Cleanup will cancel a pending frame and remove all listeners whenever navigation is rebuilt or the view is destroyed.

### 3. Keep the active TOC entry visible

`PostToc` will own a reference to its navigation viewport and expose the rendered button for the active item. When `activeId` changes, it will compare the active button's bounds with the TOC navigation viewport:

- Desktop: adjust only the TOC's vertical scroll position when the item is above or below the visible area.
- Mobile: adjust only the horizontal navigation scroll position when the active pill is left or right of the visible area.

The adjustment will use a small edge margin and reduced-motion-aware behavior. It must not call an API that can also scroll the article page vertically.

Programmatic alignment will be skipped when the active item is already fully visible, preventing constant small movements while reading.

### 4. Preserve navigation semantics

TOC buttons remain real `button` elements and retain `aria-current="location"` for the active entry. Clicking an item continues to call `scrollIntoView` on the target heading, using smooth scrolling unless the operating system requests reduced motion.

The clicked item may be marked active immediately for responsive feedback, but the reading-position calculation remains authoritative after scrolling progresses or completes.

## Component and File Scope

Expected production changes:

- `frontend/src/styles/base.css`
  - change root horizontal clipping from `hidden` to `clip`;
- `frontend/src/styles/post.css`
  - preserve desktop sticky behavior and make the mobile horizontal TOC sticky, layered, and independently scrollable;
- `frontend/src/composables/useTableOfContents.js`
  - replace narrow `IntersectionObserver` activation with animation-frame-throttled reading-position tracking;
  - add listener/frame cleanup;
- `frontend/src/components/post/PostToc.vue`
  - keep the active entry visible within the desktop or mobile TOC viewport.

`PostView.vue` should remain unchanged unless implementation reveals that a TOC DOM reference must be passed explicitly. Any such change must stay limited to navigation wiring.

## Edge Cases

- An article without `h2`/`h3` continues to render no TOC and keeps the centered single-column layout.
- A short TOC does not scroll unnecessarily.
- Duplicate or absent heading IDs continue to receive the existing generated fallback IDs.
- Clicking a subsection near the end of the document activates and reveals it.
- Reversing direction updates to the preceding section.
- At the document bottom, the final heading is active even if it cannot reach the reading line.
- Resizing across the 920px breakpoint changes TOC alignment from vertical to horizontal without moving the article's vertical scroll position.
- Reduced-motion mode avoids smooth animation for both article navigation and TOC alignment.

## Validation

### Automated checks

- Run `npm run build` in `frontend/`.
- Run `backend/.venv/Scripts/python.exe -m pytest backend/tests -q` with a clean `--basetemp` path if required by Windows ACLs.
- Run `git diff --check`.

### Real-browser checks

Use a temporary database and the generated long article; do not write to `storage/blog.db`.

Desktop at 1440 x 900:

- scroll from chapter 1 to chapters 8 and 14;
- reverse-scroll to an earlier chapter;
- verify the TOC remains at its sticky offset;
- verify the highlighted entry matches the current reading section;
- verify the highlighted entry is visible after the TOC itself has scrolled;
- click an early and a late TOC item and verify heading alignment.

Mobile at approximately 390 x 844:

- verify the horizontal TOC sticks below the mobile header;
- verify article text does not show through it;
- scroll through enough sections to move the active item beyond the first screen;
- verify the TOC moves horizontally without changing the article's vertical position;
- click a TOC item and verify the target heading is not hidden beneath the sticky UI.

Also inspect browser console output for new errors.

## Acceptance Criteria

The fix is accepted when:

- the desktop TOC remains visible while the article reading layout is on screen;
- the mobile horizontal TOC remains visible below the header while reading;
- the active entry correctly follows normal, reverse, rapid, restored, and end-of-document scrolling;
- the active entry remains visible in the TOC's own scroll viewport on both layouts;
- TOC alignment never causes an unintended vertical article jump;
- frontend build, backend tests, and real-browser verification pass.
