// Display formatting shared by the pages: dates in UK style (UTC, as in the mailbox), percentages and units.

const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC",
});
const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const SHORT_DAY = new Intl.DateTimeFormat("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const DAY_DATE = new Intl.DateTimeFormat("en-GB", {
  weekday: "short", day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
});

/** "Mon 2 Feb, 10:48" — when a message was sent (UTC, like the source data). */
export function formatDateTime(iso: string): string {
  return DATE_TIME.format(new Date(iso));
}

/** "20 Feb 2026" — a calendar date such as a deadline. */
export function formatDate(iso: string): string {
  return DATE.format(new Date(iso));
}

/** "Sun 1 Feb" — a day in the mailbox, when the year is obvious. */
export function formatShortDay(iso: string): string {
  return SHORT_DAY.format(new Date(iso));
}

/** "Fri 20 Feb 2026" — the as-of date, with its weekday so "today" is unambiguous. */
export function formatDayDate(iso: string): string {
  return DAY_DATE.format(new Date(iso));
}

/** 0.6 → "60%": a stored 0–1 value (confidence, a threshold) as a whole percentage. */
export function percent(fraction: number): string {
  return `${Math.round(fraction * 100)}%`;
}

/** 9 → "9 working days", 1 → "1 working day": waiting time with its unit, never "wd". */
export function workingDays(days: number): string {
  return `${days} working day${days === 1 ? "" : "s"}`;
}

/**
 * Show a stored rule detail with its ISO dates in the UI's style, changing nothing else:
 * "2026-02-03 (17 day(s) overdue)" → "3 Feb 2026 (17 day(s) overdue)".
 */
export function tidyDetail(detail: string): string {
  return detail.replace(/\b\d{4}-\d{2}-\d{2}\b/g, (iso) => formatDate(iso));
}
