import { Languages, LogOut, Sparkles } from "lucide-react";
import { NavLink, useNavigate } from "react-router-dom";

import { Brand } from "@/components/layout/brand";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { NAV_ITEMS } from "@/lib/navigation";
import { cn } from "@/lib/utils";

function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/admin/login", { replace: true });
  }

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

            return (
              <NavLink
                key={item.id}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-all focus-visible:ring-2 focus-visible:ring-sidebar-ring focus-visible:outline-none",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-accent-foreground shadow-xs"
                      : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground"
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        "grid size-9 shrink-0 place-items-center rounded-xl border transition-colors",
                        isActive
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
                    {isActive && (
                      <span className="size-1.5 shrink-0 rounded-full bg-primary" />
                    )}
                  </>
                )}
              </NavLink>
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

        <div className="mt-3 flex items-center gap-2 rounded-xl border border-sidebar-border bg-card/40 px-3 py-2">
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold">
              {user?.name || "Clinic admin"}
            </p>
            <p className="truncate text-[10px] text-muted-foreground">
              {user?.email}
            </p>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={handleLogout}
            aria-label="Sign out"
            title="Sign out"
          >
            <LogOut />
          </Button>
        </div>

        <p className="px-1 pt-4 text-[10px] text-muted-foreground/70">
          Clinic Voice AI · Receptionist workspace
        </p>
      </div>
    </aside>
  );
}

export { Sidebar };
