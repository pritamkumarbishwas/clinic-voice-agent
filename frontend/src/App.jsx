import { lazy, useEffect } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";

import { ProtectedRoute } from "@/components/auth/protected-route";
import { SessionBootstrap } from "@/components/auth/session-bootstrap";
import { AdminLayout } from "@/components/layout/admin-layout";
import { PublicLayout } from "@/components/layout/public-layout";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import Login from "./Login";

const Appointments = lazy(() => import("./Appointments"));
const CallLog = lazy(() => import("./CallLog"));
const ClinicSettings = lazy(() => import("./ClinicSettings"));
const Doctors = lazy(() => import("./Doctors"));
const Knowledge = lazy(() => import("./Knowledge"));
const LatencyDashboard = lazy(() => import("./LatencyDashboard"));
const LiveCall = lazy(() => import("./LiveCall"));

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);

  return null;
}

export default function App() {
  return (
    <ThemeProvider>
      <TooltipProvider>
        <SessionBootstrap />
        <ScrollToTop />
        <Routes>
          <Route element={<PublicLayout />}>
            <Route index element={<LiveCall />} />
          </Route>

          <Route path="/admin/login" element={<Login />} />

          <Route element={<ProtectedRoute />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<Navigate to="live" replace />} />
              <Route path="live" element={<LiveCall admin />} />
              <Route path="appointments" element={<Appointments />} />
              <Route path="calls" element={<CallLog />} />
              <Route path="doctors" element={<Doctors />} />
              <Route path="clinic" element={<ClinicSettings />} />
              <Route path="knowledge" element={<Knowledge />} />
              <Route path="latency" element={<LatencyDashboard />} />
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <Toaster />
      </TooltipProvider>
    </ThemeProvider>
  );
}
