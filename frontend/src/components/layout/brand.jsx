import { AudioLines } from "lucide-react";

import { cn } from "@/lib/utils";

function Brand({ compact = false, className }) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div className="relative grid size-10 shrink-0 place-items-center rounded-2xl bg-linear-to-br from-primary to-chart-2 text-primary-foreground shadow-lg shadow-primary/20">
        <AudioLines className="size-5" strokeWidth={2.2} />
        <span className="absolute -top-0.5 -right-0.5 size-3 rounded-full border-2 border-sidebar bg-success" />
      </div>

      {!compact && (
        <div className="min-w-0">
          <p className="truncate text-sm font-extrabold tracking-tight">
            Clinic Voice AI
          </p>
          <p className="truncate text-[10px] font-semibold tracking-[0.17em] text-muted-foreground uppercase">
            Receptionist console
          </p>
        </div>
      )}
    </div>
  );
}

export { Brand };
