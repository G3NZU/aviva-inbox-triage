import type { ThreadRow as ThreadRowData } from "../types";
import { humanise } from "../format";
import PriorityBadge from "./PriorityBadge";

/** The "why" hint: the priority's explanation and every rule that fired, on hover or keyboard focus. */
function Why({ row }: { row: ThreadRowData }) {
  if (row.rules_fired.length === 0) return null;
  return (
    <span className="group relative inline-block" tabIndex={0} onClick={(event) => event.stopPropagation()}>
      <span className="cursor-help rounded border border-slate-300 px-1.5 py-0.5 text-xs text-slate-600">why</span>
      <span className="invisible absolute right-0 z-10 mt-1 w-96 rounded-md bg-slate-900 p-3 text-left text-xs text-white shadow-lg group-hover:visible group-focus:visible">
        <span className="mb-2 block font-semibold">{row.explanation}</span>
        {row.rules_fired.map((rule) => (
          <span key={rule} className="block font-mono text-slate-300">{rule}</span>
        ))}
      </span>
    </span>
  );
}

/** One line of the workload table: priority, what to do, the claim, who, age, and why. Click to open. */
export default function ThreadRow({ row, onOpen }: { row: ThreadRowData; onOpen: (key: string) => void }) {
  return (
    <tr onClick={() => onOpen(row.key)} className="cursor-pointer border-t border-slate-200 align-top hover:bg-slate-50">
      <td className="px-3 py-2">
        <PriorityBadge level={row.level} bucket={row.bucket} />
      </td>
      <td className="px-3 py-2">
        <div className="font-medium">{row.action_summary || row.subject}</div>
        {row.action_summary && <div className="text-xs text-slate-500">{row.subject}</div>}
      </td>
      <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{row.claim_ref ?? "—"}</td>
      <td className="px-3 py-2 text-sm">
        {row.sender_type ? humanise(row.sender_type) : "—"}
        <div className="text-xs text-slate-500">{row.sender}</div>
      </td>
      <td className="whitespace-nowrap px-3 py-2 text-right text-sm">{row.age_days} d</td>
      <td className="px-3 py-2 text-right">
        <Why row={row} />
      </td>
    </tr>
  );
}
