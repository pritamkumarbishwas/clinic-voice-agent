import { useCallback, useEffect, useState } from "react";

import { apiGet } from "@/lib/api";

function useApiHealth() {
  const [status, setStatus] = useState("checking");

  const fetchHealth = useCallback(
    () =>
      apiGet("/api/health")
        .then((data) => (data?.status === "healthy" ? "healthy" : "degraded"))
        .catch(() => "offline"),
    []
  );

  const check = useCallback(async () => {
    const nextStatus = await fetchHealth();
    setStatus(nextStatus);
  }, [fetchHealth]);

  useEffect(() => {
    let active = true;

    function sync() {
      fetchHealth().then((nextStatus) => {
        if (active) setStatus(nextStatus);
      });
    }

    sync();
    const interval = window.setInterval(sync, 60_000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [fetchHealth]);

  return { status, check };
}

export { useApiHealth };
