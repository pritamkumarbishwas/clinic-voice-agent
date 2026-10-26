import { ShieldCheck } from "lucide-react";
import { Suspense } from "react";
import { Link, Outlet } from "react-router-dom";

import { Brand } from "@/components/layout/brand";
import { ViewFallback } from "@/components/shared/view-fallback";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";

function PublicLayout() {
  return (
    <div className="min-h-screen bg-background surface-glow">
      <header className="sticky top-0 z-30 border-b border-border/70 bg-background/82 backdrop-blur-xl">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center gap-3 px-4 sm:px-6 lg:px-8">
          <Brand />

          <div className="ml-auto flex items-center gap-2">
            <ThemeToggle />
            <Button asChild variant="outline" size="sm">
              <Link to="/admin/login">
                <ShieldCheck />
                Staff login
              </Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
        <Suspense fallback={<ViewFallback />}>
          <Outlet />
        </Suspense>
      </main>
    </div>
  );
}

export { PublicLayout };
