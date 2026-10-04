/*
 * Placeholders in the shape of the page, shown only when a load is slow: they fade in after 300 ms (pure CSS,
 * no timer), so a fast local load shows nothing and nothing flashes. The bars pulse only if motion is allowed.
 */

const DELAYED = "animate-[fade-in_150ms_var(--ease-enter)_300ms_both]";

/** One grey bar of the given width. */
function Bar({ width, tall = false }: { width: string; tall?: boolean }) {
  return <div className={`rounded bg-sunken motion-safe:animate-pulse ${tall ? "h-4" : "h-3"} ${width}`} />;
}

/** The workload while its first load is slow: a few rows (the count cards render on their own). */
export function WorkloadSkeleton() {
  return (
    <div aria-hidden="true" className={`space-y-4 ${DELAYED}`}>
      <div className="space-y-4 rounded-xl border border-line bg-surface p-4">
        {Array.from({ length: 5 }, (_, i) => (
          <div key={i} className="space-y-2"><Bar width="w-3/4" tall /><Bar width="w-1/2" /></div>
        ))}
      </div>
    </div>
  );
}

/** A thread while its first load is slow: the decision band and one email. */
export function ThreadSkeleton() {
  return (
    <div aria-hidden="true" className={`space-y-4 ${DELAYED}`}>
      <Bar width="w-2/3" tall />
      <div className="space-y-2 rounded-lg border border-line bg-surface p-4"><Bar width="w-1/4" /><Bar width="w-5/6" tall /></div>
      <div className="space-y-2 rounded-lg border border-line bg-surface p-4">
        <Bar width="w-1/3" /><Bar width="w-full" /><Bar width="w-11/12" /><Bar width="w-4/5" />
      </div>
    </div>
  );
}
