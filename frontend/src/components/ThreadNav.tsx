import Icon from "./Icon";

/**
 * The bar above a thread: back to where you came from, and (when opened from the workload) the thread's place
 * in your list with Previous / Next, so you can work down the queue without going back each time.
 * Props: where Back goes, the list of thread keys in screen order (if any), the current key, and the handlers.
 */
export default function ThreadNav({ backLabel, queue, current, onBack, onGo }: {
  backLabel: string; queue?: string[]; current: string; onBack: () => void; onGo: (key: string) => void;
}) {
  const index = queue ? queue.indexOf(current) : -1;
  const prev = index > 0 ? queue![index - 1] : null;
  const next = index >= 0 && index < queue!.length - 1 ? queue![index + 1] : null;
  const link = "inline-flex min-h-6 items-center gap-1 rounded px-1 text-sm text-accent hover:text-accent-strong "
    + "hover:underline disabled:text-ink-3 disabled:no-underline";
  return (
    <nav aria-label="Thread" className="flex flex-wrap items-center justify-between gap-2">
      <button type="button" onClick={onBack} className={link}>
        <Icon name="chevronLeft" className="size-4" /> {backLabel}
      </button>
      {index >= 0 && (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-ink-2 tabular-nums"><span className="sr-only">Thread </span>{index + 1} of {queue!.length}</span>
          <button type="button" onClick={() => prev && onGo(prev)} disabled={!prev} className={link}>
            <Icon name="chevronLeft" className="size-4" /> Previous
          </button>
          <button type="button" onClick={() => next && onGo(next)} disabled={!next} className={link}>
            Next <Icon name="chevronRight" className="size-4" />
          </button>
        </div>
      )}
    </nav>
  );
}
