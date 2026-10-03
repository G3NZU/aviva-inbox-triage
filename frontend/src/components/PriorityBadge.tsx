import type { Bucket, Level } from "../types";

const STYLES: Record<string, string> = {
  P1: "bg-red-600 text-white",
  P2: "bg-amber-500 text-white",
  P3: "bg-sky-600 text-white",
  P4: "bg-slate-300 text-slate-700",
  review: "bg-violet-600 text-white",
  ignore: "bg-slate-100 text-slate-500",
  untriaged: "bg-slate-100 text-slate-400",
};
const LABELS: Record<string, string> = { review: "Review", ignore: "Ignore", untriaged: "—" };

/** A coloured pill for a thread's place in the workload: P1–P4, "Review" or "Ignore". */
export default function PriorityBadge({ level, bucket }: { level: Level | null; bucket: Bucket | null }) {
  const key = bucket === "review" || bucket === "ignore" ? bucket : (level ?? "untriaged");
  const label = LABELS[key] ?? key;
  return (
    <span className={`inline-block min-w-14 rounded-full px-2 py-0.5 text-center text-xs font-semibold ${STYLES[key]}`}>
      {label}
    </span>
  );
}
