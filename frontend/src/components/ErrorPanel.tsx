import { ApiError } from "../api";
import Icon from "./Icon";

/** The cause in plain words: the API is not running, or it answered with an error. */
function plainCause(error: Error): { title: string; advice: string } {
  if (error instanceof ApiError && error.kind === "network") {
    return { title: "Can't reach the triage service", advice: "Start the API (see the README) and try again." };
  }
  return { title: "Something went wrong", advice: "The service answered with an error; the technical detail says why." };
}

/**
 * Shown where the content would be when a request fails: a plain cause, a way to try again, and the
 * API's own message folded under "Technical detail". role="alert" so screen readers hear it at once.
 * Props: the error, and an optional retry handler.
 */
export default function ErrorPanel({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const { title, advice } = plainCause(error);
  return (
    <div role="alert" className="rounded-lg border border-p1-line bg-p1-bg p-4 text-p1-fg">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <Icon name="error" className="size-5 text-p1-mark" />
        <p className="font-semibold">{title}</p>
        <p className="text-sm">{advice}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="ml-auto rounded-md border border-p1-fg bg-surface px-3 py-1
            text-sm font-semibold hover:bg-p1-bg">
            Try again
          </button>
        )}
      </div>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer">Technical detail</summary>
        <p className="mt-1 font-mono text-xs">{error.message}</p>
      </details>
    </div>
  );
}
