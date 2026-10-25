import { Bot, UserRound } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatTime } from "@/lib/format";

function TranscriptMessage({ item }) {
  const isAssistant = item.role === "assistant";
  const Icon = isAssistant ? Bot : UserRound;
  const timestamp = item.receivedAt ? formatTime(item.receivedAt) : "";

  return (
    <div
      className={cn(
        "flex items-start gap-2.5 animate-fade-up",
        !isAssistant && "flex-row-reverse"
      )}
    >
      <div
        className={cn(
          "mt-0.5 grid size-8 shrink-0 place-items-center rounded-xl border",
          isAssistant
            ? "border-primary/15 bg-primary/10 text-primary"
            : "border-border bg-muted text-muted-foreground"
        )}
      >
        <Icon className="size-4" />
      </div>

      <div
        className={cn(
          "min-w-0 max-w-[84%]",
          !isAssistant && "flex flex-col items-end"
        )}
      >
        <div
          className={cn(
            "mb-1 flex items-center gap-2 text-[10px] font-semibold text-muted-foreground",
            !isAssistant && "flex-row-reverse"
          )}
        >
          <span>{isAssistant ? "AI receptionist" : "Caller"}</span>
          {timestamp && <span className="font-normal opacity-70">{timestamp}</span>}
        </div>

        <div
          className={cn(
            "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed shadow-xs",
            isAssistant
              ? "rounded-tl-md border border-primary/10 bg-primary/8"
              : "rounded-tr-md border border-border/70 bg-muted/70",
            !item.isFinal && "border-dashed opacity-75"
          )}
        >
          {item.text}
          {!item.isFinal && (
            <span className="ml-2 inline-flex items-center gap-1 text-[10px] font-semibold text-muted-foreground">
              <span className="size-1.5 animate-pulse rounded-full bg-primary" />
              Listening
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export { TranscriptMessage };
