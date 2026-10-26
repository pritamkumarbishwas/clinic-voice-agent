import { useEffect, useState } from "react";
import {
  Activity,
  CalendarCheck2,
  FlaskConical,
  Gauge,
  Hand,
  PhoneCall,
  RefreshCw,
  Timer,
  TriangleAlert,
} from "lucide-react";

import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { MetricCard } from "@/components/shared/metric-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiGet } from "@/lib/api";
import {
  formatMs,
  formatNumber,
  formatPercent,
  pluralize,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const STAGES = [
  { key: "endpoint_latency_ms", label: "Endpoint decision" },
  { key: "stt_latency_ms", label: "Speech to final transcript" },
  { key: "llm_latency_ms", label: "LLM first token" },
  { key: "tts_latency_ms", label: "TTS first audio" },
  { key: "end_to_audio_ms", label: "Speech to response audio" },
  { key: "playback_latency_ms", label: "Audio to playback" },
];

function p95Tone(value) {
  if (typeof value !== "number") {
    return { label: "No data", variant: "outline" };
  }
  if (value <= 300) return { label: "Fast", variant: "success" };
  if (value <= 700) return { label: "Watch", variant: "warning" };
  return { label: "Slow", variant: "destructive" };
}

function barTone(value) {
  if (typeof value !== "number") return "bg-muted-foreground/25";
  if (value <= 300) return "bg-success";
  if (value <= 700) return "bg-warning";
  return "bg-destructive";
}

function LatencySkeleton() {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="rounded-2xl border bg-card p-5">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-4 h-7 w-16" />
            <Skeleton className="mt-2 h-2.5 w-28" />
          </div>
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
        <div className="rounded-2xl border bg-card p-5">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="mt-2 h-3 w-56" />
          <div className="mt-5 space-y-4">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-8 w-full" />
            ))}
          </div>
        </div>
        <div className="rounded-2xl border bg-card p-5">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="mt-2 h-3 w-48" />
          <div className="mt-5 space-y-5">
            {Array.from({ length: 6 }).map((_, index) => (
              <Skeleton key={index} className="h-9 w-full" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LatencyDashboard() {
  const [report, setReport] = useState({});
  const [runs, setRuns] = useState([]);
  const [runId, setRunId] = useState("all");
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    apiGet("/api/analytics/runs", { signal: controller.signal })
      .then((data) => setRuns(data.items ?? []))
      .catch(() => {
        // The report still works when the run list is unavailable.
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    const controller = new AbortController();
    const path =
      runId === "all"
        ? "/api/analytics/latency"
        : `/api/analytics/latency?run_id=${encodeURIComponent(runId)}`;

    apiGet(path, { signal: controller.signal })
      .then((data) => {
        setReport(data);
        setError("");
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [reloadKey, runId]);

  function refresh() {
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  function changeRun(value) {
    setLoading(true);
    setRunId(value);
  }

  const metrics = report.metrics ?? {};
  const rows = STAGES.map((stage) => ({
    ...stage,
    ...(metrics[stage.key] || {}),
  }));

  const slowest = rows
    .filter((row) => typeof row.p95_ms === "number")
    .sort((a, b) => b.p95_ms - a.p95_ms)[0];

  const maxValue = Math.max(1, ...rows.map((row) => row.p95_ms || 0));
  const hasSamples = rows.some((row) => (row.count || 0) > 0);
  const perCall = report.per_call ?? [];
  const activeRun = runs.find((run) => run.run_id === runId);

  return (
    <div className="space-y-5 animate-fade-up">
      <PageHeader
        icon={Gauge}
        eyebrow="Performance"
        title="Latency dashboard"
        description="Understand where response time is spent across endpointing, speech recognition, language generation, and audio playback."
        actions={
          <>
            <Select value={runId} onValueChange={changeRun}>
              <SelectTrigger
                aria-label="Benchmark run"
                className="w-full bg-card sm:w-64"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <FlaskConical className="size-4 shrink-0 text-muted-foreground" />
                  <SelectValue />
                </span>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All calls</SelectItem>
                {runs.map((run) => (
                  <SelectItem key={run.run_id} value={run.run_id}>
                    {run.run_id} ({run.call_count}{" "}
                    {pluralize(run.call_count, "call")})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button
              type="button"
              variant="outline"
              onClick={refresh}
              disabled={loading}
              className="w-full sm:w-auto"
            >
              <RefreshCw className={cn(loading && "animate-spin")} />
              Refresh
            </Button>
          </>
        }
      />

      {error && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Could not load latency metrics</AlertTitle>
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
        <LatencySkeleton />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
            <MetricCard
              icon={PhoneCall}
              label="Calls measured"
              value={formatNumber(report.calls_measured ?? 0)}
              hint={activeRun ? `Run ${activeRun.run_id}` : "All recorded calls"}
              tone="primary"
            />
            <MetricCard
              icon={Activity}
              label="Turns measured"
              value={formatNumber(report.turns_measured ?? 0)}
              hint="Conversation turns with timing data"
              tone="info"
            />
            <MetricCard
              icon={CalendarCheck2}
              label="Booking success"
              value={formatPercent(report.booking_success_rate)}
              hint={`${formatNumber(report.booking_successes ?? 0)} booked ${pluralize(report.booking_successes ?? 0, "appointment")}`}
              tone="success"
            />
            <MetricCard
              icon={Hand}
              label="Barge-ins"
              value={formatNumber(report.barge_in_count ?? 0)}
              hint="Caller interruptions recorded"
              tone="warning"
            />
            <MetricCard
              icon={Timer}
              label="Largest p95"
              value={slowest ? formatMs(slowest.p95_ms) : "n/a"}
              hint={slowest?.label || "No stage samples yet"}
              tone="destructive"
              className="col-span-2 md:col-span-1"
            />
          </div>

          {!hasSamples && (
            <Alert variant="info">
              <Gauge />
              <AlertTitle>No latency samples yet</AlertTitle>
              <AlertDescription>
                Complete a live call and the stage timings will appear here
                automatically.
              </AlertDescription>
            </Alert>
          )}

          <div className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
            <Card className="gap-0 overflow-hidden">
              <CardHeader className="pb-4">
                <CardTitle className="text-sm">Stage breakdown</CardTitle>
                <CardDescription>
                  Percentile timings across every measured conversation turn.
                </CardDescription>
              </CardHeader>

              <CardContent className="p-0">
                <div className="divide-y divide-border/70 md:hidden">
                  {rows.map((row) => {
                    const tone = p95Tone(row.p95_ms);
                    return (
                      <div key={row.key} className="px-5 py-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="text-xs font-semibold">{row.label}</p>
                            <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                              {row.key}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <span className="text-[10px] text-muted-foreground">
                              {formatNumber(row.count ?? 0)}{" "}
                              {pluralize(row.count ?? 0, "sample")}
                            </span>
                            <Badge variant={tone.variant}>{tone.label}</Badge>
                          </div>
                        </div>
                        <div className="mt-3 grid grid-cols-3 gap-2 rounded-xl bg-muted/40 p-2.5">
                          {[
                            ["p50", row.p50_ms],
                            ["p95", row.p95_ms],
                            ["p99", row.p99_ms],
                          ].map(([label, value], index) => (
                            <div
                              key={label}
                              className={cn(
                                "text-center",
                                index === 1 && "border-x border-border/70"
                              )}
                            >
                              <p className="text-[9px] font-semibold tracking-wider text-muted-foreground uppercase">
                                {label}
                              </p>
                              <p
                                className={cn(
                                  "mt-0.5 font-mono text-xs tabular-nums",
                                  index === 1
                                    ? "font-semibold"
                                    : "text-muted-foreground"
                                )}
                              >
                                {formatMs(value)}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>

                <div className="hidden md:block">
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/30 hover:bg-muted/30">
                        <TableHead className="pl-5">Stage</TableHead>
                        <TableHead className="text-right">Samples</TableHead>
                        <TableHead className="text-right">p50</TableHead>
                        <TableHead className="text-right">p95</TableHead>
                        <TableHead className="text-right">p99</TableHead>
                        <TableHead className="pr-5 text-right">Health</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((row) => {
                        const tone = p95Tone(row.p95_ms);
                        return (
                          <TableRow key={row.key}>
                            <TableCell className="min-w-52 pl-5">
                              <p className="text-xs font-semibold">{row.label}</p>
                              <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                                {row.key}
                              </p>
                            </TableCell>
                            <TableCell className="text-right text-xs text-muted-foreground">
                              {formatNumber(row.count ?? 0)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-xs tabular-nums">
                              {formatMs(row.p50_ms)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-xs font-semibold tabular-nums">
                              {formatMs(row.p95_ms)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-xs tabular-nums text-muted-foreground">
                              {formatMs(row.p99_ms)}
                            </TableCell>
                            <TableCell className="pr-5 text-right">
                              <Badge variant={tone.variant}>{tone.label}</Badge>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">p95 comparison</CardTitle>
                <CardDescription>
                  Lower is better. The longest stage is highlighted by color.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4 pt-3">
                {rows.map((row) => {
                  const width = ((row.p95_ms || 0) / maxValue) * 100;
                  return (
                    <div key={row.key}>
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-[11px] font-medium text-muted-foreground">
                          {row.label}
                        </p>
                        <p className="shrink-0 font-mono text-xs font-semibold tabular-nums">
                          {formatMs(row.p95_ms)}
                        </p>
                      </div>
                      <Progress
                        value={width}
                        className="mt-1.5 h-2 bg-muted"
                        indicatorClassName={barTone(row.p95_ms)}
                      />
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </div>

          <Card className="gap-0 overflow-hidden">
            <CardHeader className="pb-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-sm">Slowest calls</CardTitle>
                  <CardDescription>
                    Median stage timings per call, ranked by speech-to-audio
                    latency.
                  </CardDescription>
                </div>
                <Badge variant="outline">
                  {perCall.length} {pluralize(perCall.length, "call")}
                </Badge>
              </div>
            </CardHeader>

            <CardContent className="p-0">
              {perCall.length === 0 ? (
                <div className="p-5">
                  <EmptyState
                    icon={PhoneCall}
                    title="No per-call samples"
                    description="Per-call timing appears after a conversation has been measured."
                    compact
                  />
                </div>
              ) : (
                <>
                  <div className="divide-y divide-border/70 md:hidden">
                    {perCall.slice(0, 10).map((call) => (
                      <div key={call.call_id} className="px-5 py-4">
                        <div className="flex items-center justify-between gap-3">
                          <p
                            className="truncate font-mono text-xs font-semibold"
                            title={call.call_id}
                          >
                            {call.call_id}
                          </p>
                          {call.run_id ? (
                            <Badge variant="outline" className="shrink-0 text-[9px]">
                              {call.run_id}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">
                              n/a
                            </span>
                          )}
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          {[
                            ["Turns", formatNumber(call.turns ?? 0)],
                            ["E2E p50", formatMs(call.end_to_audio_ms)],
                            ["LLM p50", formatMs(call.llm_latency_ms)],
                            ["TTS p50", formatMs(call.tts_latency_ms)],
                          ].map(([label, value], index) => (
                            <div
                              key={label}
                              className="rounded-lg bg-muted/40 px-3 py-2"
                            >
                              <p className="text-[9px] font-semibold tracking-wider text-muted-foreground uppercase">
                                {label}
                              </p>
                              <p
                                className={cn(
                                  "mt-0.5 font-mono text-xs tabular-nums",
                                  index === 0 && "text-muted-foreground"
                                )}
                              >
                                {value}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="hidden md:block">
                    <Table>
                      <TableHeader>
                        <TableRow className="bg-muted/30 hover:bg-muted/30">
                          <TableHead className="pl-5">Call</TableHead>
                          <TableHead>Run</TableHead>
                          <TableHead className="text-right">Turns</TableHead>
                          <TableHead className="text-right">E2E p50</TableHead>
                          <TableHead className="text-right">LLM p50</TableHead>
                          <TableHead className="pr-5 text-right">TTS p50</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {perCall.slice(0, 10).map((call) => (
                          <TableRow key={call.call_id}>
                            <TableCell className="max-w-[22rem] pl-5">
                              <p
                                className="truncate font-mono text-xs font-semibold"
                                title={call.call_id}
                              >
                                {call.call_id}
                              </p>
                            </TableCell>
                            <TableCell>
                              {call.run_id ? (
                                <Badge variant="outline" className="text-[9px]">
                                  {call.run_id}
                                </Badge>
                              ) : (
                                <span className="text-xs text-muted-foreground">
                                  n/a
                                </span>
                              )}
                            </TableCell>
                            <TableCell className="text-right text-xs text-muted-foreground">
                              {formatNumber(call.turns ?? 0)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-xs font-semibold tabular-nums">
                              {formatMs(call.end_to_audio_ms)}
                            </TableCell>
                            <TableCell className="text-right font-mono text-xs tabular-nums">
                              {formatMs(call.llm_latency_ms)}
                            </TableCell>
                            <TableCell className="pr-5 text-right font-mono text-xs tabular-nums">
                              {formatMs(call.tts_latency_ms)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
