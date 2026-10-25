import { lazy, Suspense, useEffect, useState } from "react";

import { AppShell } from "@/components/layout/app-shell";
import { ThemeProvider } from "@/components/theme-provider";
import { Skeleton } from "@/components/ui/skeleton";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useApiHealth } from "@/hooks/use-api-health";

const CallLog = lazy(() => import("./CallLog"));
const LatencyDashboard = lazy(() => import("./LatencyDashboard"));
const LiveCall = lazy(() => import("./LiveCall"));

function ViewFallback() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading view">
      <div className="space-y-2">
        <Skeleton className="h-2.5 w-24" />
        <Skeleton className="h-8 w-64 max-w-full" />
        <Skeleton className="h-3.5 w-full max-w-xl" />
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Skeleton className="h-80 rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
    </div>
  );
}

export default function App() {
  const [view, setView] = useState("live");
  const { status, check } = useApiHealth();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [view]);

  return (
    <ThemeProvider>
      <TooltipProvider>
        <AppShell
          view={view}
          onViewChange={setView}
          healthStatus={status}
          onCheckHealth={check}
        >
          <Suspense fallback={<ViewFallback />}>
            {view === "live" && <LiveCall />}
            {view === "calls" && <CallLog onGoLive={() => setView("live")} />}
            {view === "latency" && <LatencyDashboard />}
          </Suspense>
        </AppShell>
        <Toaster />
      </TooltipProvider>
    </ThemeProvider>
  );
}
