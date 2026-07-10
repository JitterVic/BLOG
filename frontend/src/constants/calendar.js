export const CALENDAR_SCROLLBAR_HIDDEN_CLASS = "calendar-scrollbar-hidden";

let scrollbarHiddenLockCount = 0;

function applyCalendarScrollbarHidden(enabled) {
  if (typeof document === "undefined") {
    return;
  }

  document.documentElement.classList.toggle(CALENDAR_SCROLLBAR_HIDDEN_CLASS, enabled);
  document.body.classList.toggle(CALENDAR_SCROLLBAR_HIDDEN_CLASS, enabled);
}

export function acquireCalendarScrollbarHidden() {
  scrollbarHiddenLockCount += 1;
  applyCalendarScrollbarHidden(true);
}

export function releaseCalendarScrollbarHidden() {
  scrollbarHiddenLockCount = Math.max(scrollbarHiddenLockCount - 1, 0);
  applyCalendarScrollbarHidden(scrollbarHiddenLockCount > 0);
}
