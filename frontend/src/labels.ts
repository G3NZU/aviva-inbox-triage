// Every code the API sends, in plain words: one place for the UI's vocabulary.
// Each Record is typed against a union in types.ts, so a missing label fails the build.
// Wording only: which card a thread is in and which rules set its priority come from the API.
import { tidyDetail } from "./format";
import type { ActionType, Card, Category, LineOfBusiness, Rating, Reason, SenderType, Signal } from "./types";

interface CardWords {
  label: string; // the one name for this state, used on cards, sections and chips
  compact: string; // the short chip text, only inside a section that already says the label
  hint: string; // one visible line saying what the state means
  zeroHint: string; // what an empty card says
  empty: string; // what an empty section says
}

export const CARD: Record<Card, CardWords> = {
  P1: { label: "P1 · Act today", compact: "P1", hint: "A risk, or a deadline due now", zeroHint: "None right now",
    empty: "Nothing to act on today." },
  P2: { label: "P2 · This week", compact: "P2", hint: "Someone is waiting on us", zeroHint: "None right now",
    empty: "Nothing due this week." },
  review: { label: "Needs a check", compact: "Check", hint: "The AI was unsure: you decide",
    zeroHint: "None: every reading passed",
    empty: "Nothing needs a check: the AI was sure enough of every reading." },
  P3: { label: "P3 · Normal", compact: "P3", hint: "Needs action, nothing urgent", zeroHint: "None right now",
    empty: "None right now: every thread that needs action is Act today, This week or Needs a check." },
  archive: { label: "P4 · No action needed", compact: "P4", hint: "For information, or resolved",
    zeroHint: "None right now", empty: "No threads here." },
  ignore: { label: "Not claims work", compact: "Not claims", hint: "Spam, adverts or misdirected",
    zeroHint: "None right now", empty: "No threads here." },
  untriaged: { label: "Not read yet", compact: "Not read", hint: "The AI has not read it yet", zeroHint: "None",
    empty: "Every thread has been read." },
};

/** Said instead of a zero card's hint or an empty section's sentence while some threads are unread. */
export const PARTIAL_EMPTY = "None among the threads read so far";

/** What the AI can spot in a thread (signals), with definitions worded from the triage prompt. */
export const SIGNALS: Record<Signal, { label: string; definition: string }> = {
  fnol: { label: "New claim reported (FNOL)",
    definition: "First notification of loss: a loss reported for the first time, or a request to open a claim." },
  injury: { label: "Injury", definition: "Someone has been physically hurt, or it is a personal injury claim." },
  make_safe_urgent: { label: "Urgent make-safe",
    definition: "Property is unsafe or open to the weather right now and needs emergency work." },
  complaint: { label: "Complaint",
    definition: "The sender is unhappy with our service, or makes or escalates a formal complaint." },
  legal_threat: { label: "Legal action threatened",
    definition: "Solicitors act for someone, a letter of claim arrives, or proceedings are threatened." },
  regulatory: { label: "Regulatory issue",
    definition: "Regulatory exposure, such as a data breach, complaint-handling rules or the Financial Ombudsman." },
  fraud_flag: { label: "Possible fraud",
    definition: "Fraud is suspected or being investigated, or details do not add up." },
  vulnerable_customer: { label: "Vulnerable customer",
    definition: "Signs of vulnerability: a health condition or disability, older age, severe distress, "
      + "children or tenants at risk, or financial hardship." },
  repeat_chase: { label: "Chased again", definition: "The sender is following up a request we have not answered." },
  payment_or_authority_pending: { label: "Payment or approval pending",
    definition: "An invoice, a payment or an authority to proceed is waiting for our decision." },
  already_resolved: { label: "Already resolved", definition: "The latest email shows nothing more is owed." },
  parse_error: { label: "AI reading failed",
    definition: "The AI's reply could not be read, or the AI could not be reached, so a person checks the thread. The code sets this, not the AI." },
};

export const SENDER: Record<SenderType, string> = {
  customer: "Customer", broker: "Broker", repairer_supplier: "Repairer or supplier", solicitor: "Solicitor",
  loss_adjuster: "Loss adjuster", internal: "Pinnacle staff", automated: "Automated system",
  unknown: "Unknown sender",
};

/** Descriptions of the work, never commands: the app recommends and does nothing itself. */
export const ACTION: Record<ActionType, string> = {
  respond: "Respond to the sender", approve_authorise: "Approve or authorise", investigate: "Investigate",
  chase_third_party: "Chase a third party", open_new_claim: "Open a new claim", review_document: "Review a document",
  escalate: "Escalate", none: "No action",
};

export const CATEGORY: Record<Category, string> = {
  action_required: "Needs action", informational: "For information", irrelevant: "Not claims work",
};

export const LINE: Record<LineOfBusiness, string> = {
  home: "Home", motor: "Motor", liability: "Liability", unknown: "Not stated",
};

export const RATING: Record<Rating, string> = { high: "High", medium: "Medium", low: "Low" };

/** Rule codes whose detail is a signal name: the reason reads as that signal's label. */
const SIGNAL_RULES = new Set(["p1_risk_signal", "p2_waiting_signal"]);

/** Fixed words for rules whose detail adds nothing a handler needs. */
const RULE_WORDS: Record<string, string> = {
  p2_urgency_high: "AI rated it urgent",
  p2_importance_high: "AI rated it high-stakes",
  p3_default: "Needs action, nothing urgent",
  override_already_resolved: "Latest email says it is resolved",
  bucket_archive: "For information only",
  bucket_ignore: "Not claims work",
};

/**
 * One rule that fired, as a phrase: "Complaint", "Deadline 3 Feb 2026 (17 day(s) overdue)",
 * "Waiting on us for 14 working days". Stored details are shown as stored (dates tidied only);
 * an unknown rule shows its raw text, so nothing new is ever hidden.
 */
export function ruleText({ rule, detail }: Reason): string {
  if (SIGNAL_RULES.has(rule)) return SIGNALS[detail as Signal]?.label ?? detail;
  if (rule in RULE_WORDS) return RULE_WORDS[rule];
  if (rule === "p1_deadline_due" || rule === "p2_deadline_this_week") return `Deadline ${tidyDetail(detail)}`;
  if (rule === "p2_unanswered") return detail.charAt(0).toUpperCase() + detail.slice(1);
  if (rule === "override_low_confidence") return `AI unsure: confidence ${detail}`;
  return detail ? `${rule}: ${detail}` : rule;
}

/** The phrases for the rules that set the level, e.g. "Complaint · Regulatory issue". */
export function decidingText(reasons: Reason[]): string {
  return reasons.filter((r) => r.sets_level).map(ruleText).join(" · ");
}
