import { cn } from "@/lib/utils";

const STATES = {
  checking: {
    label: "Checking API",
    dot: "bg-warning",
    text: "text-muted-foreground",
  },
  healthy: {
    label: "API connected",
    dot: "bg-success",
    text: "text-muted-foreground",
  },
  degraded: {
    label: "API degraded",
    dot: "bg-warning",
    text: "text-warning",
  },
  offline: {
    label: "API offline",
    dot: "bg-destructive",
    text: "text-destructive",
  },
};

function ConnectionStatus({ status, onRetry }) {
  const state = STATES[status] || STATES.checking;

  return (
    <button
      type="button"
      onClick={onRetry}
      title="Check API connection"
      aria-label={`${state.label}. Check API connection`}
      className="group flex items-center gap-2 rounded-full border border-border/80 bg-card/70 px-2.5 py-1.5 text-[11px] font-semibold shadow-xs transition-colors hover:bg-muted/70 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <span className="relative flex size-2 shrink-0">
        {status === "checking" && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-warning opacity-60" />
        )}
        <span
          className={cn("relative inline-flex size-2 rounded-full", state.dot)}
        />
      </span>
      <span className={cn("hidden sm:inline", state.text)}>{state.label}</span>
    </button>
  );
}

export { ConnectionStatus };
