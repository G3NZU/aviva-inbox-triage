import { LINE } from "../labels";
import type { LineOfBusiness } from "../types";

const OPTIONS: (LineOfBusiness | null)[] = [null, "home", "motor", "liability", "unknown"];

/**
 * The one line-of-business filter: a labelled dropdown (All lines, Home, Motor, Liability, Not stated). One
 * control instead of a row of buttons; no counts, as it filters what the cards already counted.
 * Props: the chosen line (null = all) and a setter.
 */
export default function LineFilter({ value, onChange }: {
  value: LineOfBusiness | null; onChange: (line: LineOfBusiness | null) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-ink-2">
      Line of business
      <select value={value ?? ""} onChange={(e) => onChange((e.target.value || null) as LineOfBusiness | null)}
        className="rounded-md border border-line-strong bg-surface py-1 pl-2 pr-1 text-ink">
        {OPTIONS.map((option) => (
          <option key={option ?? "all"} value={option ?? ""}>{option ? LINE[option] : "All lines"}</option>
        ))}
      </select>
    </label>
  );
}
