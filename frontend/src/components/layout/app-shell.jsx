import { ChevronRight, LogOut } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { Brand } from "@/components/layout/brand";
import { ConnectionStatus } from "@/components/layout/connection-status";
import { MobileNav } from "@/components/layout/mobile-nav";
import { Sidebar } from "@/components/layout/sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/use-auth";
import { getNavItem } from "@/lib/navigation";

function AppShell({ healthStatus, onCheckHealth, children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const current = getNavItem(location.pathname);
  const CurrentIcon = current.icon;

  async function handleLogout() {
    await logout();
    navigate("/admin/login", { replace: true });
  }

  return (
    <div className="min-h-screen bg-background surface-glow">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-primary-foreground"
      >
        Skip to content
      </a>
      <Sidebar />

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
        </header>

        <main
          id="main-content"
          className="mx-auto w-full max-w-7xl px-4 pt-6 pb-28 sm:px-6 sm:pt-8 lg:px-8 lg:pb-10"
        >
          {children}
        </main>
      </div>

      <MobileNav />
    </div>
  );
}

export { AppShell };
