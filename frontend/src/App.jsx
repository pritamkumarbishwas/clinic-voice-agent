import { useState } from "react";

import CallLog from "./CallLog";
import LatencyDashboard from "./LatencyDashboard";
import LiveCall from "./LiveCall";
import { AppShell } from "@/components/layout/app-shell";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useApiHealth } from "@/hooks/use-api-health";

export default function App() {
  const [view, setView] = useState("live");
  const { status, check } = useApiHealth();

  return (
    <ThemeProvider>
      <TooltipProvider>
        <AppShell
          view={view}
          onViewChange={setView}
          healthStatus={status}
          onCheckHealth={check}
        >
          {view === "live" && <LiveCall />}
          {view === "calls" && <CallLog onGoLive={() => setView("live")} />}
          {view === "latency" && <LatencyDashboard />}
        </AppShell>
        <Toaster />
      </TooltipProvider>
    </ThemeProvider>
  );
}
