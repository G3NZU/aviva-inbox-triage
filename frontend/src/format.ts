// Display formatting shared by the pages: dates in UK style (UTC, as in the mailbox) and readable labels.

const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC",
});
const DATE = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

/** "Mon 2 Feb, 10:48" — when a message was sent (UTC, like the source data). */
export function formatDateTime(iso: string): string {
  return DATE_TIME.format(new Date(iso));
}

/** "20 Feb 2026" — a calendar date such as the as-of date or a deadline. */
export function formatDate(iso: string): string {
  return DATE.format(new Date(iso));
}

/** "payment_or_authority_pending" → "payment or authority pending". */
export function humanise(code: string): string {
  return code.replaceAll("_", " ");
}
