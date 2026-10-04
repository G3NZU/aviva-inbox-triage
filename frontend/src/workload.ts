// How the workload list is arranged: sections in a fixed order, each keeping the API's sort.
// Arrangement only: the card each thread belongs to comes from the API (ThreadRow.card).
import type { Card, LineOfBusiness, ThreadRow } from "./types";

/**
 * Section order, most urgent first. "Needs a check" follows "This week" because the API stores review
 * threads at level P2 and sorts them with P2; the no-action groups come last.
 */
export const SECTION_ORDER: Card[] = ["P1", "P2", "review", "P3", "archive", "ignore", "untriaged"];

/** Groups that need no action: folded at the bottom of the list until opened. */
export const NO_ACTION: ReadonlySet<Card> = new Set<Card>(["archive", "ignore"]);

/**
 * Split rows into sections by their card. A stable partition: each section keeps the API's order
 * (most urgent level first, then oldest first). Every card in SECTION_ORDER gets an entry, even if empty.
 */
export function groupByCard(rows: ThreadRow[]): Map<Card, ThreadRow[]> {
  const groups = new Map<Card, ThreadRow[]>(SECTION_ORDER.map((card) => [card, []]));
  for (const row of rows) groups.get(row.card)?.push(row);
  return groups;
}

/** True when a row passes the chosen card and line of business (unset = any). Compares stored fields only. */
export function matches(row: ThreadRow, card: Card | null, line: LineOfBusiness | null): boolean {
  return (card === null || row.card === card) && (line === null || row.line_of_business === line);
}
