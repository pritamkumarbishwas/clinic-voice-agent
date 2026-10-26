import { Suspense } from "react";
import { Outlet } from "react-router-dom";

import { AppShell } from "@/components/layout/app-shell";
import { ViewFallback } from "@/components/shared/view-fallback";
import { useApiHealth } from "@/hooks/use-api-health";

function AdminLayout() {
  const { status, check } = useApiHealth();

  return (
    <AppShell healthStatus={status} onCheckHealth={check}>
      <Suspense fallback={<ViewFallback />}>
        <Outlet />
      </Suspense>
    </AppShell>
  );
}

export { AdminLayout };
