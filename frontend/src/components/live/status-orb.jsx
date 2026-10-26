import { useEffect, useState } from "react";
import {
  AudioLines,
  Loader2,
  Mic,
  PhoneOff,
  TriangleAlert,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { formatDuration } from "@/lib/format";

const PHASES = {
  idle: {
    title: "Ready when you are",
    icon: Mic,
    core: "border-primary/15 bg-primary/8 text-primary",
    ring: "border-primary/10",
  },
  connecting: {
    title: "Connecting you",
    icon: Loader2,
    core: "border-warning/20 bg-warning/10 text-warning",
    ring: "border-warning/15",
  },
  waiting: {
    title: "Receptionist joining",
    icon: Loader2,
    core: "border-warning/20 bg-warning/10 text-warning",
    ring: "border-warning/15",
  },
  live: {
    title: "You're live",
    icon: AudioLines,
    core: "border-primary/25 bg-primary text-primary-foreground shadow-xl shadow-primary/25",
    ring: "border-primary/20",
  },
  reconnecting: {
    title: "Reconnecting",
    icon: Loader2,
    core: "border-warning/20 bg-warning/10 text-warning",
    ring: "border-warning/15",
  },
  ended: {
    title: "Thanks for calling",
    icon: PhoneOff,
    core: "border-border bg-muted text-muted-foreground",
    ring: "border-border",
  },
  error: {
    title: "Couldn't connect",
    icon: TriangleAlert,
    core: "border-destructive/20 bg-destructive/10 text-destructive",
    ring: "border-destructive/15",
  },
};

function StatusOrb({ phase, status, startedAt }) {
  const [now, setNow] = useState(0);
  const config = PHASES[phase] || PHASES.idle;
  const Icon = config.icon;
  const showTimer = phase === "live" || phase === "reconnecting";
  const elapsed =
    showTimer && startedAt
      ? Math.max(0, Math.floor((now - startedAt) / 1000))
      : 0;

  useEffect(() => {
    if (!showTimer || !startedAt) return undefined;

    const tick = () => setNow(Date.now());
    const timeout = window.setTimeout(tick, 0);
    const interval = window.setInterval(tick, 1000);

    return () => {
      window.clearTimeout(timeout);
      window.clearInterval(interval);
    };
  }, [showTimer, startedAt]);

  return (
    <div className="flex flex-col items-center py-4 text-center">
      <div className="relative grid size-36 place-items-center">
        {phase === "live" && (
          <>
            <span className="absolute size-32 rounded-full border border-primary/25 animate-live-ring" />
            <span
              className="absolute size-32 rounded-full border border-primary/20 animate-live-ring"
              style={{ animationDelay: "0.8s" }}
            />
          </>
        )}

        <div
          className={cn(
            "relative grid size-28 place-items-center rounded-full border-2",
            config.ring,
            phase === "live" && "bg-primary/5"
          )}
        >
          <div
            className={cn(
              "grid size-20 place-items-center rounded-full border",
              config.core
            )}
          >
            <Icon
              className={cn(
                "size-8",
                ["connecting", "waiting", "reconnecting"].includes(phase) &&
                  "animate-spin"
              )}
              strokeWidth={phase === "live" ? 1.8 : 2}
            />
          </div>
        </div>
      </div>

      <p className="mt-4 text-lg font-extrabold tracking-tight">
        {config.title}
      </p>
      <p className="mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground">
        {status}
      </p>

      {showTimer && (
        <div className="mt-3 flex items-center gap-3">
          {phase === "live" && (
            <div className="flex h-5 items-center gap-0.5 text-primary">
              {[0, 1, 2, 3, 4].map((bar) => (
                <span
                  key={bar}
                  className="h-4 w-0.5 origin-center rounded-full bg-current animate-wave"
                  style={{ animationDelay: `${bar * 110}ms` }}
                />
              ))}
            </div>
          )}
          <span className="font-mono text-sm font-semibold tabular-nums">
            {formatDuration(elapsed)}
          </span>
        </div>
      )}
    </div>
  );
}

export { StatusOrb };
