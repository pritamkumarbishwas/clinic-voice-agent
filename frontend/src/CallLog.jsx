import { useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  History,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { CallDetailSheet } from "@/components/calls/call-detail-sheet";
import { CallFilters } from "@/components/calls/call-filters";
import { CallList, CallListSkeleton } from "@/components/calls/call-list";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getApiErrorMessage } from "@/lib/api-error";
import { formatNumber, pluralize } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  useGetCallQuery,
  useListCallsQuery,
  useListRunsQuery,
  useRequeueAnalysisMutation,
} from "@/store/api";

export default function CallLog() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [runFilter, setRunFilter] = useState("all");
  const [outcomeFilter, setOutcomeFilter] = useState("all");
  const [sentimentFilter, setSentimentFilter] = useState("all");
  const [detailOpen, setDetailOpen] = useState(false);
  const [activeCallId, setActiveCallId] = useState("");

  const callsQuery = useListCallsQuery({
    page,
    pageSize: 20,
    runId: runFilter === "all" ? undefined : runFilter,
    outcome: outcomeFilter === "all" ? undefined : outcomeFilter,
    sentiment: sentimentFilter === "all" ? undefined : sentimentFilter,
  });
  const runsQuery = useListRunsQuery();
  const detailQuery = useGetCallQuery(activeCallId, {
    skip: !activeCallId,
    refetchOnMountOrArgChange: true,
  });
  const [requeueAnalysis, { isLoading: analysisRetrying }] =
    useRequeueAnalysisMutation();

  const calls = callsQuery.currentData?.items ?? [];
  const runs = runsQuery.data?.items ?? [];
  const pages = Math.max(1, callsQuery.currentData?.total_pages ?? 1);
  const total = callsQuery.currentData?.total ?? 0;
  const loading =
    callsQuery.isLoading ||
    (callsQuery.isFetching && !callsQuery.currentData);
  const error = callsQuery.isError
    ? getApiErrorMessage(callsQuery.error, "Could not load calls")
    : "";

  const detail = detailQuery.currentData ?? null;
  const detailLoading =
    Boolean(activeCallId) &&
    (detailQuery.isLoading || (detailQuery.isFetching && !detail));
  const detailError = detailQuery.isError
    ? getApiErrorMessage(detailQuery.error, "Could not load call")
    : "";

  const hasFilters =
    runFilter !== "all" ||
    outcomeFilter !== "all" ||
    sentimentFilter !== "all";

  function refresh() {
    void callsQuery.refetch();
    void runsQuery.refetch();
  }

  function changeRun(value) {
    setPage(1);
    setRunFilter(value);
  }

  function changeOutcome(value) {
    setPage(1);
    setOutcomeFilter(value);
  }

  function changeSentiment(value) {
    setPage(1);
    setSentimentFilter(value);
  }

  function resetFilters() {
    setPage(1);
    setRunFilter("all");
    setOutcomeFilter("all");
    setSentimentFilter("all");
  }

  function goToPage(nextPage) {
    if (nextPage < 1 || nextPage > pages || nextPage === page) return;
    setPage(nextPage);
  }

  function openCall(callId) {
    setDetailOpen(true);
    setActiveCallId(callId);
  }

  function handleSheetChange(open) {
    setDetailOpen(open);

    if (!open) {
      setActiveCallId("");
    }
  }

  function retryDetail() {
    if (activeCallId) void detailQuery.refetch();
  }

  async function retryAnalysis(callId) {
    try {
      await requeueAnalysis(callId).unwrap();
      toast.success("Analysis requeued", {
        description: "The worker will process this call shortly.",
      });
    } catch (err) {
      toast.error("Could not requeue analysis", {
        description: getApiErrorMessage(err),
      });
    }
  }

  return (
    <div className="space-y-5 animate-fade-up">
      <PageHeader
        icon={History}
        eyebrow="Call log"
        title="Conversation history"
        description="Review completed calls, booking outcomes, transcripts, and conversation-level latency."
        actions={
          <>
            <Badge variant="outline" className="px-3 py-1">
              {formatNumber(total)} {pluralize(total, "call")}
            </Badge>
            <Button
              type="button"
              variant="outline"
              onClick={refresh}
              disabled={callsQuery.isFetching}
            >
              <RefreshCw
                className={cn(callsQuery.isFetching && "animate-spin")}
              />
              Refresh
            </Button>
          </>
        }
      />

      <CallFilters
        runs={runs}
        runFilter={runFilter}
        onRunChange={changeRun}
        outcomeFilter={outcomeFilter}
        onOutcomeChange={changeOutcome}
        sentimentFilter={sentimentFilter}
        onSentimentChange={changeSentiment}
        onReset={resetFilters}
        hasFilters={hasFilters}
      />

      {error && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Could not load calls</AlertTitle>
          <AlertDescription>
            <p>{error}</p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={refresh}
              className="mt-2"
            >
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {loading ? (
        <CallListSkeleton />
      ) : calls.length === 0 ? (
        <EmptyState
          icon={History}
          title={
            hasFilters ? "No calls match these filters" : "No calls recorded yet"
          }
          description={
            hasFilters
              ? "Try clearing one or more filters to see more conversations."
              : "Complete a test call and the conversation will appear here with its outcome, analysis, and latency."
          }
          action={
            hasFilters ? (
              <Button type="button" variant="outline" onClick={resetFilters}>
                Clear filters
              </Button>
            ) : (
              <Button
                type="button"
                onClick={() => navigate("/admin/live")}
              >
                Start a call
              </Button>
            )
          }
        />
      ) : (
        <CallList calls={calls} onOpenCall={openCall} />
      )}

      {!loading && calls.length > 0 && (
        <div className="flex flex-col items-center justify-between gap-3 rounded-2xl border border-border/80 bg-card px-4 py-3 sm:flex-row">
          <p className="text-xs text-muted-foreground">
            Page {page} of {pages} · {formatNumber(total)}{" "}
            {pluralize(total, "call")}
          </p>
          <div className="flex w-full gap-2 sm:w-auto">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => goToPage(page - 1)}
              disabled={page <= 1}
              className="flex-1 sm:flex-none"
            >
              <ChevronLeft />
              Previous
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => goToPage(page + 1)}
              disabled={page >= pages}
              className="flex-1 sm:flex-none"
            >
              Next
              <ChevronRight />
            </Button>
          </div>
        </div>
      )}

      <CallDetailSheet
        open={detailOpen}
        onOpenChange={handleSheetChange}
        detail={detail}
        loading={detailLoading}
        error={detailError}
        onRetry={retryDetail}
        retrying={detailQuery.isFetching}
        retryingAnalysis={analysisRetrying}
        onRetryAnalysis={retryAnalysis}
      />
    </div>
  );
}
