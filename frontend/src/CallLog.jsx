import { useEffect, useRef, useState } from "react";
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
import { apiGet, apiPost } from "@/lib/api";
import { formatNumber, pluralize } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function CallLog() {
  const navigate = useNavigate();
  const [calls, setCalls] = useState([]);
  const [runs, setRuns] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [runFilter, setRunFilter] = useState("all");
  const [outcomeFilter, setOutcomeFilter] = useState("all");
  const [sentimentFilter, setSentimentFilter] = useState("all");

  const [detailOpen, setDetailOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [activeCallId, setActiveCallId] = useState("");
  const [analysisRetrying, setAnalysisRetrying] = useState(false);

  const detailAbortRef = useRef(null);

  useEffect(() => {
    const controller = new AbortController();

    apiGet("/api/analytics/runs", { signal: controller.signal })
      .then((data) => setRuns(data.items ?? []))
      .catch(() => {
        // Run filtering is optional; the call list still works without it.
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({
      page: String(page),
      page_size: "20",
    });

    if (runFilter !== "all") params.set("run_id", runFilter);
    if (outcomeFilter !== "all") params.set("outcome", outcomeFilter);
    if (sentimentFilter !== "all") params.set("sentiment", sentimentFilter);

    apiGet(`/api/calls?${params.toString()}`, {
      signal: controller.signal,
    })
      .then((data) => {
        setCalls(data.items ?? []);
        setPages(Math.max(1, data.total_pages ?? 1));
        setTotal(data.total ?? 0);
        setError("");
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [page, runFilter, outcomeFilter, sentimentFilter, reloadKey]);

  useEffect(() => {
    return () => detailAbortRef.current?.abort();
  }, []);

  const hasFilters =
    runFilter !== "all" ||
    outcomeFilter !== "all" ||
    sentimentFilter !== "all";

  function refresh() {
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  function changeRun(value) {
    setLoading(true);
    setPage(1);
    setRunFilter(value);
  }

  function changeOutcome(value) {
    setLoading(true);
    setPage(1);
    setOutcomeFilter(value);
  }

  function changeSentiment(value) {
    setLoading(true);
    setPage(1);
    setSentimentFilter(value);
  }

  function resetFilters() {
    setLoading(true);
    setPage(1);
    setRunFilter("all");
    setOutcomeFilter("all");
    setSentimentFilter("all");
  }

  function goToPage(nextPage) {
    if (nextPage < 1 || nextPage > pages || nextPage === page) return;
    setLoading(true);
    setPage(nextPage);
  }

  async function loadCall(callId) {
    detailAbortRef.current?.abort();

    const controller = new AbortController();
    detailAbortRef.current = controller;

    setActiveCallId(callId);
    setSelected(null);
    setDetailError("");
    setDetailLoading(true);

    try {
      const data = await apiGet(`/api/calls/${encodeURIComponent(callId)}`, {
        signal: controller.signal,
      });

      if (!controller.signal.aborted) setSelected(data);
    } catch (err) {
      if (err.name !== "AbortError") setDetailError(err.message);
    } finally {
      if (detailAbortRef.current === controller) {
        detailAbortRef.current = null;
        setDetailLoading(false);
      }
    }
  }

  function openCall(callId) {
    setDetailOpen(true);
    loadCall(callId);
  }

  function handleSheetChange(open) {
    setDetailOpen(open);

    if (!open) {
      detailAbortRef.current?.abort();
      detailAbortRef.current = null;
      setSelected(null);
      setDetailError("");
      setDetailLoading(false);
      setActiveCallId("");
    }
  }

  function retryDetail() {
    if (activeCallId) loadCall(activeCallId);
  }

  async function retryAnalysis(callId) {
    setAnalysisRetrying(true);

    try {
      await apiPost(`/api/calls/${encodeURIComponent(callId)}/analyze`);
      setSelected((previous) =>
        previous
          ? {
              ...previous,
              call: {
                ...previous.call,
                analysis_status: "pending",
                analysis_error: null,
              },
            }
          : previous
      );
      toast.success("Analysis requeued", {
        description: "The worker will process this call shortly.",
      });
      setReloadKey((value) => value + 1);
    } catch (err) {
      toast.error("Could not requeue analysis", {
        description: err.message,
      });
    } finally {
      setAnalysisRetrying(false);
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
              disabled={loading}
            >
              <RefreshCw className={cn(loading && "animate-spin")} />
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
        detail={selected}
        loading={detailLoading}
        error={detailError}
        onRetry={retryDetail}
        retrying={detailLoading}
        retryingAnalysis={analysisRetrying}
        onRetryAnalysis={retryAnalysis}
      />
    </div>
  );
}
