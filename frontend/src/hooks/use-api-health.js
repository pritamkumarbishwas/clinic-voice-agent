import { useGetHealthQuery } from "@/store/api";

function useApiHealth() {
  const { data, isError, isLoading, refetch } = useGetHealthQuery(
    undefined,
    { pollingInterval: 60_000 }
  );

  const status = isError
    ? "offline"
    : isLoading
      ? "checking"
      : data?.status === "healthy"
        ? "healthy"
        : "degraded";

  return { status, check: refetch };
}

export { useApiHealth };
