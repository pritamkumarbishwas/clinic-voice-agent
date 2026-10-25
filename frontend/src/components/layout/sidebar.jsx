import { Languages, Sparkles } from "lucide-react";

import { Brand } from "@/components/layout/brand";
import { Badge } from "@/components/ui/badge";
import { NAV_ITEMS } from "@/lib/navigation";
import { cn } from "@/lib/utils";

function Sidebar({ view, onChange }) {
  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-72 flex-col border-r border-sidebar-border bg-sidebar lg:flex">
      <div className="px-5 py-6">
        <Brand />
      </div>

      <div className="px-3">
        <p className="px-3 pb-2 text-[10px] font-bold tracking-[0.16em] text-muted-foreground uppercase">
          Workspace
        </p>
        <nav aria-label="Sections" className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = view === item.id;

            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onChange(item.id)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "group flex w-full cursor-pointer items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none",
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-xs"
                    : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
                )}
              >
                <span
                  className={cn(
                    "grid size-9 shrink-0 place-items-center rounded-xl border transition-colors",
                    active
                      ? "border-primary/15 bg-primary/10 text-primary"
                      : "border-border/60 bg-card/50 text-muted-foreground group-hover:text-foreground"
                  )}
                >
                  <Icon className="size-4.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold">
                    {item.label}
                  </span>
                  <span className="block truncate text-[11px] text-muted-foreground">
                    {item.description}
                  </span>
                </span>
                {active && (
                  <span className="size-1.5 shrink-0 rounded-full bg-primary" />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="mt-auto p-4">
        <div className="rounded-2xl border border-sidebar-border bg-card/60 p-4">
          <div className="flex items-center gap-2">
            <span className="grid size-8 place-items-center rounded-lg bg-primary/10 text-primary">
              <Sparkles className="size-4" />
            </span>
            <div>
              <p className="text-xs font-bold">Voice stack ready</p>
              <p className="text-[10px] text-muted-foreground">
                LiveKit + Sarvam
              </p>
            </div>
          </div>

          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
            Natural conversations with live availability checks and appointment
            booking.
          </p>

          <div className="mt-3 flex flex-wrap gap-1.5">
            {["Hindi", "English", "Hinglish"].map((language) => (
              <Badge key={language} variant="outline" className="text-[10px]">
                {language}
              </Badge>
            ))}
          </div>

          <div className="mt-3 flex items-center gap-1.5 text-[10px] font-medium text-muted-foreground">
            <Languages className="size-3.5" />
            Multilingual by default
          </div>
        </div>

        <p className="px-1 pt-4 text-[10px] text-muted-foreground/70">
          Clinic Voice AI · Receptionist workspace
        </p>
      </div>
    </aside>
  );
}

export { Sidebar };
