import { ChevronRight } from "lucide-react";

import { ConnectionStatus } from "@/components/layout/connection-status";
import { Brand } from "@/components/layout/brand";
import { MobileNav } from "@/components/layout/mobile-nav";
import { Sidebar } from "@/components/layout/sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { getNavItem } from "@/lib/navigation";

function AppShell({
  view,
  onViewChange,
  healthStatus,
  onCheckHealth,
  children,
}) {
  const current = getNavItem(view);
  const CurrentIcon = current.icon;

  return (
    <div className="min-h-screen bg-background surface-glow">
      <Sidebar view={view} onChange={onViewChange} />

      <div className="lg:pl-72">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-border/70 bg-background/82 px-4 backdrop-blur-xl sm:px-6 lg:px-8">
          <div className="lg:hidden">
            <Brand />
          </div>

          <div className="hidden min-w-0 items-center gap-2 lg:flex">
            <span className="text-xs font-medium text-muted-foreground">
              Workspace
            </span>
            <ChevronRight className="size-3.5 text-muted-foreground/60" />
            <CurrentIcon className="size-4 text-muted-foreground" />
            <span className="truncate text-sm font-semibold">
              {current.label}
            </span>
          </div>

          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <ConnectionStatus status={healthStatus} onRetry={onCheckHealth} />
            <ThemeToggle />
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 pt-6 pb-28 sm:px-6 sm:pt-8 lg:px-8 lg:pb-10">
          {children}
        </main>
      </div>

      <MobileNav view={view} onChange={onViewChange} />
    </div>
  );
}

export { AppShell };
