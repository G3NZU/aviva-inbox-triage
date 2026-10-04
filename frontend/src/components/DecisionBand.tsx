import type { ReactNode } from "react";
import { formatDate, workingDays } from "../format";
import type { ThreadDetail } from "../types";
import { NO_ACTION } from "../workload";
import { EDGE } from "./PriorityBadge";

/**
 * The suggested next step: the AI's action summary, or, when there is none, words chosen by the API's card,
 * so an unread thread or a failed AI reply is never shown as "no action needed".
 */
function nextStep(detail: ThreadDetail): string {
  const action = detail.triage?.result.action_summary;
  if (action) return action;
  const card = detail.thread.card;
  if (card === "untriaged") return "Not read by the AI yet: re-run triage, or read the emails and decide.";
  if (card === "review") return "The AI was unsure, or its reply could not be used: read the emails and decide.";
  return NO_ACTION.has(card) ? "No action needed." : "Read the emails and decide the next step.";
}

/**
 * Whether someone is waiting on us, from stored facts only: the API's waiting days and whether the latest
 * email came from Pinnacle (from_internal). No-action threads state the wait as a plain fact.
 */
function waitingText(detail: ThreadDetail): string {
  const latest = detail.messages[detail.messages.length - 1];
  if (latest?.from_internal) return "No: we sent the latest email";
  if (!detail.priority) return "Not counted yet"; // no priority stored: there is no wait to show
  const days = detail.priority.waiting_days;
  return NO_ACTION.has(detail.thread.card) ? `Last outside email: ${workingDays(days)} ago` : workingDays(days);
}

/**
 * The first thing on a thread page: the suggested next step (the AI's action summary) and the two facts that
 * say how pressing it is: who is waiting, and any deadline.
 * Props: the thread detail and the (i) button for "Waiting on us".
 */
export default function DecisionBand({ detail, waitingHelp }: { detail: ThreadDetail; waitingHelp?: ReactNode }) {
  const triage = detail.triage?.result;
  return (
    <section aria-label="Suggested next step"
      className={`rounded-lg border border-l-4 border-line bg-surface p-4 ${EDGE[detail.thread.card]}`}>
      <p className="text-xs text-ink-2">Suggested next step</p>
      <p className="mt-1 max-w-prose font-semibold">{nextStep(detail)}</p>
      <dl className="mt-3 flex flex-wrap gap-x-10 gap-y-2 text-sm">
        <div className="flex items-center gap-2">
          <dt className="inline-flex items-center gap-1 text-ink-2">Waiting on us {waitingHelp}</dt>
          <dd className="font-semibold tabular-nums">{waitingText(detail)}</dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="text-ink-2">Deadline mentioned</dt>
          <dd className="font-semibold tabular-nums">
            {triage?.deadline_mentioned ? formatDate(triage.deadline_mentioned) : "None stated"}
          </dd>
        </div>
      </dl>
    </section>
  );
}
