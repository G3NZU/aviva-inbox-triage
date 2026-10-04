// The definitions a handler may need once, in plain words: listed under "About this data", plus the one (i)
// button ("Waiting on us"). Any number in them (thresholds, the as-of date) comes from GET /summary, so the
// help always matches backend/app/config.py: change a threshold there and these sentences change with it.
import { formatDayDate, percent } from "./format";
import type { Card, Summary } from "./types";

/** What a definition can quote: the rules' thresholds and the as-of date, both from the API. */
export type HelpFacts = Pick<Summary, "policy" | "as_of">;
type Definition = (facts: HelpFacts) => string;

/** One definition per workload group, listed under "About this data". */
export const CARD_HELP: Record<Card, Definition> = {
  P1: ({ policy }) => "a risk to a customer or to us (a complaint, an injury, urgent make-safe work, a legal threat, "
    + "a regulatory issue, possible fraud or a vulnerable customer), or a deadline in the emails that is overdue or "
    + `due within ${policy.p1_deadline_days} days.`,
  P2: ({ policy }) => "someone is waiting on us: they chased, reported a new claim or await a payment or an approval, "
    + `or their latest email has waited more than ${policy.unanswered_working_days} working days. A deadline within `
    + `${policy.p2_deadline_days} days, or the AI rating it urgent or high-stakes, also puts a thread here.`,
  review: ({ policy }) => `the AI was less than ${percent(policy.confidence_threshold)} sure, or its reply could not `
    + "be used: a person reads the emails and decides. Nothing in this group is archived.",
  P3: () => "it needs action, but no Act today or This week rule applied.",
  archive: () => "for information, or the latest email says it is resolved. It stays in the mailbox.",
  ignore: () => "spam, marketing or mail that is not about a claim, listed so you can check it. Nothing is deleted.",
  untriaged: () => "the AI has not read it yet: choose Re-run triage.",
};

type Term = "asOf" | "waiting" | "senderFlag";

/** The other definitions: "Waiting on us" (behind its (i)), the as-of date and the sender's flag. */
export const HELP: Record<Term, Definition> = {
  asOf: ({ as_of }) => `The mailbox is a snapshot that ends on ${formatDayDate(as_of)}, so "today", waiting times `
    + "and deadlines are counted to that date.",
  waiting: ({ policy, as_of }) => "Working days (Monday to Friday) since the latest email from someone outside "
    + `Pinnacle, counted to ${formatDayDate(as_of)}. 0 means we sent the latest email, or it arrived that day. More than `
    + `${policy.unanswered_working_days} working days makes a thread that needs action at least This week; the clock `
    + "shows when that rule set its priority. Bank holidays are not taken off.",
  senderFlag: () => "A sender's own \"high importance\" flag is shown on the email but never changes a priority.",
};
