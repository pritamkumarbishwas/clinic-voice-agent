import {
  Bot,
  CalendarCheck2,
  CalendarX2,
  ChevronDown,
  Clock3,
  Hand,
  LayoutDashboard,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Sparkles,
  Tag,
  Timer,
  TriangleAlert,
  UserRound,
  Wrench,
} from "lucide-react";

import { EmptyState } from "@/components/shared/empty-state";
import {
  AnalysisBadge,
  OutcomeBadge,
  SentimentBadge,
} from "@/components/shared/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  formatCallDuration,
  formatDateTime,
  formatMs,
  formatTime,
  titleCase,
} from "@/lib/format";
import { cn } from "@/lib/utils";

const TAB_CLASS =
  "h-11 flex-none cursor-pointer gap-1 rounded-none border-x-0 border-t-0 border-b-2 border-transparent px-1.5 text-[11px] sm:gap-1.5 sm:px-3 sm:text-sm data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:text-primary data-[state=active]:shadow-none";

function prettyValue(value) {
  if (value === null || value === undefined || value === "") return "";

  if (typeof value === "string") {
    const trimmed = value.trim();
    const looksLikeJson =
      (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
      (trimmed.startsWith("[") && trimmed.endsWith("]"));

    if (looksLikeJson) {
      try {
        return JSON.stringify(JSON.parse(trimmed), null, 2);
      } catch {
        return value;
      }
    }

    return value;
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function DetailStat({ icon: Icon, label, value }) {
  return (
    <div className="rounded-xl border border-border/70 bg-muted/20 p-3">
      <div className="flex items-center gap-1.5 text-[10px] font-semibold tracking-wide text-muted-foreground uppercase">
        <Icon className="size-3.5" />
        {label}
      </div>
      <p
        className="mt-1.5 line-clamp-2 text-sm font-semibold break-words"
        title={String(value)}
      >
        {value}
      </p>
    </div>
  );
}

function TurnCard({ turn, index }) {
  const isAssistant = turn.role === "assistant";

  const metrics = isAssistant
    ? [
        { label: "LLM", value: turn.llm_latency_ms },
        { label: "TTS", value: turn.tts_latency_ms },
        { label: "E2E", value: turn.end_to_audio_ms },
        { label: "Playback", value: turn.playback_latency_ms },
      ]
    : [
        { label: "Endpoint", value: turn.endpoint_latency_ms },
        { label: "STT", value: turn.stt_latency_ms },
      ];

  return (
    <div className="rounded-xl border border-border/70 bg-card p-3.5">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "grid size-7 place-items-center rounded-lg",
              isAssistant
                ? "bg-primary/10 text-primary"
                : "bg-muted text-muted-foreground"
            )}
          >
            {isAssistant ? (
              <Bot className="size-3.5" />
            ) : (
              <UserRound className="size-3.5" />
            )}
          </span>
          <p className="text-xs font-semibold">
            {isAssistant ? "AI receptionist" : "Caller"}
          </p>
        </div>
        <span className="text-[10px] text-muted-foreground">
          Turn {index + 1}
          {turn.started_at ? ` · ${formatTime(turn.started_at)}` : ""}
        </span>
      </div>

      <div
        className={cn(
          "mt-3 grid gap-2",
          isAssistant ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-2"
        )}
      >
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="rounded-lg bg-muted/40 px-2.5 py-2"
          >
            <p className="text-[9px] font-bold tracking-wide text-muted-foreground uppercase">
              {metric.label}
            </p>
            <p className="mt-1 font-mono text-xs font-semibold tabular-nums">
              {formatMs(metric.value)}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function CallDetailSheet({
  open,
  onOpenChange,
  detail,
  loading,
  error,
  onRetry,
  retrying,
  retryingAnalysis,
  onRetryAnalysis,
}) {
  const call = detail?.call;
  const appointment = detail?.appointment;
  const turns = detail?.turn_metrics ?? [];
  const transcript = call?.transcript ?? [];
  const toolCalls = call?.tool_calls ?? [];
  const analysisStatus = call?.analysis_status || "pending";
  const summary =
    call?.summary ||
    (analysisStatus === "completed"
      ? "No summary was recorded for this call."
      : "Analysis is pending. A summary will appear here when processing completes.");

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="gap-0 p-0 sm:max-w-2xl">
        {loading ? (
          <>
            <SheetHeader>
              <SheetTitle>Loading call details</SheetTitle>
              <SheetDescription>
                Fetching the transcript, analysis, and latency samples.
              </SheetDescription>
            </SheetHeader>
            <div className="space-y-4 p-5 sm:p-7">
              <Skeleton className="h-6 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
              <div className="flex gap-2">
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-20 rounded-full" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
              <Skeleton className="h-28 w-full rounded-2xl" />
              <div className="grid gap-2 sm:grid-cols-2">
                <Skeleton className="h-20 rounded-xl" />
                <Skeleton className="h-20 rounded-xl" />
                <Skeleton className="h-20 rounded-xl" />
                <Skeleton className="h-20 rounded-xl" />
              </div>
            </div>
          </>
        ) : !call ? (
          <>
            <SheetHeader>
              <SheetTitle>Call details</SheetTitle>
              <SheetDescription>
                We could not load this conversation.
              </SheetDescription>
            </SheetHeader>
            <div className="p-5 sm:p-7">
              <Alert variant="destructive">
                <TriangleAlert />
                <AlertTitle>Could not load call</AlertTitle>
                <AlertDescription>{error || "Unknown error"}</AlertDescription>
              </Alert>
              <Button
                type="button"
                variant="outline"
                onClick={onRetry}
                disabled={retrying}
                className="mt-4"
              >
                {retrying ? (
                  <Loader2 className="animate-spin" />
                ) : (
                  <RefreshCw />
                )}
                Try again
              </Button>
            </div>
          </>
        ) : (
          <>
            <SheetHeader>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[10px] font-bold tracking-[0.17em] text-primary uppercase">
                  Call detail
                </p>
                {call.run_id && (
                  <Badge variant="outline" className="font-mono text-[9px]">
                    {call.run_id}
                  </Badge>
                )}
              </div>
              <SheetTitle className="break-all font-mono text-base sm:text-lg">
                {call.call_id}
              </SheetTitle>
              <SheetDescription>
                {formatDateTime(call.started_at)} ·{" "}
                {formatCallDuration(call)}
              </SheetDescription>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <OutcomeBadge outcome={call.booking_outcome} />
                <SentimentBadge sentiment={call.sentiment} />
                <AnalysisBadge status={analysisStatus} />
              </div>
            </SheetHeader>

            <Tabs
              defaultValue="overview"
              className="flex min-h-0 flex-1 flex-col gap-0"
            >
              <div className="border-b px-5 sm:px-7">
                <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto rounded-none bg-transparent p-0">
                  <TabsTrigger value="overview" className={TAB_CLASS}>
                    <LayoutDashboard />
                    Overview
                  </TabsTrigger>
                  <TabsTrigger value="transcript" className={TAB_CLASS}>
                    <MessageSquareText />
                    Transcript
                    <span className="hidden rounded-full bg-muted px-1.5 text-[10px] sm:inline-flex">
                      {transcript.length}
                    </span>
                  </TabsTrigger>
                  <TabsTrigger value="tools" className={TAB_CLASS}>
                    <Wrench />
                    Tools
                    <span className="hidden rounded-full bg-muted px-1.5 text-[10px] sm:inline-flex">
                      {toolCalls.length}
                    </span>
                  </TabsTrigger>
                  <TabsTrigger value="latency" className={TAB_CLASS}>
                    <Timer />
                    Latency
                  </TabsTrigger>
                </TabsList>
              </div>

              <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7">
                <TabsContent value="overview" className="space-y-4">
                  <div className="rounded-2xl border border-primary/15 bg-primary/5 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="flex items-center gap-2 text-xs font-bold text-primary">
                        <Sparkles className="size-4" />
                        AI summary
                      </p>
                      <AnalysisBadge status={analysisStatus} />
                    </div>
                    <p className="mt-2 text-sm leading-relaxed">{summary}</p>

                    {call.follow_up && (
                      <div className="mt-3 border-t border-primary/10 pt-3">
                        <p className="text-[10px] font-bold tracking-wide text-muted-foreground uppercase">
                          Follow-up
                        </p>
                        <p className="mt-1 text-sm leading-relaxed">
                          {call.follow_up}
                        </p>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
                    <DetailStat
                      icon={Clock3}
                      label="Duration"
                      value={formatCallDuration(call)}
                    />
                    <DetailStat
                      icon={Sparkles}
                      label="Intent"
                      value={call.intent || "Not captured"}
                    />
                    <DetailStat
                      icon={Tag}
                      label="Benchmark run"
                      value={call.run_id || "Unassigned"}
                    />
                    <DetailStat
                      icon={Hand}
                      label="Barge-ins"
                      value={call.barge_in_count ?? 0}
                    />
                    <DetailStat
                      icon={MessageSquareText}
                      label="Speech turns"
                      value={call.speech_count ?? 0}
                    />
                    <DetailStat
                      icon={CalendarCheck2}
                      label="Appointment"
                      value={call.appointment_id ? "Booked" : "Not booked"}
                    />
                  </div>

                  <div
                    className={cn(
                      "rounded-2xl border p-4",
                      appointment
                        ? "border-success/20 bg-success/5"
                        : "border-dashed border-border bg-muted/20"
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <span
                        className={cn(
                          "grid size-9 shrink-0 place-items-center rounded-xl",
                          appointment
                            ? "bg-success/12 text-success"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {appointment ? (
                          <CalendarCheck2 className="size-4" />
                        ) : (
                          <CalendarX2 className="size-4" />
                        )}
                      </span>

                      <div className="min-w-0 flex-1">
                        {appointment ? (
                          <>
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-xs font-bold text-success">
                                Appointment booked
                              </p>
                              <Badge variant="success">
                                {titleCase(appointment.status || "booked")}
                              </Badge>
                            </div>
                            <p className="mt-1 text-sm font-semibold">
                              {appointment.name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {appointment.phone}
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {appointment.doctor_name || "Doctor"} ·{" "}
                              {formatDateTime(appointment.start_at)}
                            </p>
                          </>
                        ) : (
                          <p className="text-xs leading-relaxed text-muted-foreground">
                            No appointment was booked for this call.
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  {call.analysis_error && (
                    <Alert variant="destructive">
                      <TriangleAlert />
                      <AlertTitle>Analysis failed</AlertTitle>
                      <AlertDescription>
                        {call.analysis_error}
                      </AlertDescription>
                    </Alert>
                  )}
                </TabsContent>

                <TabsContent value="transcript">
                  {transcript.length === 0 ? (
                    <EmptyState
                      icon={MessageSquareText}
                      title="No transcript recorded"
                      description="This call ended before any conversation was captured."
                      compact
                    />
                  ) : (
                    <div className="space-y-4">
                      {transcript.map((item, index) => {
                        const isAssistant = item.role === "assistant";
                        return (
                          <div
                            key={`${item.role}-${index}`}
                            className={cn(
                              "flex items-start gap-2.5",
                              !isAssistant && "flex-row-reverse"
                            )}
                          >
                            <span
                              className={cn(
                                "mt-0.5 grid size-8 shrink-0 place-items-center rounded-xl border",
                                isAssistant
                                  ? "border-primary/15 bg-primary/10 text-primary"
                                  : "border-border bg-muted text-muted-foreground"
                              )}
                            >
                              {isAssistant ? (
                                <Bot className="size-4" />
                              ) : (
                                <UserRound className="size-4" />
                              )}
                            </span>
                            <div
                              className={cn(
                                "max-w-[84%]",
                                !isAssistant && "flex flex-col items-end"
                              )}
                            >
                              <div
                                className={cn(
                                  "mb-1 flex items-center gap-2 text-[10px] font-semibold text-muted-foreground",
                                  !isAssistant && "flex-row-reverse"
                                )}
                              >
                                <span>
                                  {isAssistant
                                    ? "AI receptionist"
                                    : "Caller"}
                                </span>
                                {item.timestamp && (
                                  <span className="font-normal opacity-70">
                                    {formatTime(item.timestamp)}
                                  </span>
                                )}
                              </div>
                              <div
                                className={cn(
                                  "rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed",
                                  isAssistant
                                    ? "rounded-tl-md border border-primary/10 bg-primary/8"
                                    : "rounded-tr-md border border-border/70 bg-muted/70"
                                )}
                              >
                                {item.text}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="tools">
                  {toolCalls.length === 0 ? (
                    <EmptyState
                      icon={Wrench}
                      title="No tool calls recorded"
                      description="Availability checks and booking attempts will appear here."
                      compact
                    />
                  ) : (
                    <div className="space-y-2.5">
                      {toolCalls.map((tool, index) => (
                        <details
                          key={`${tool.call_id || "tool"}-${index}`}
                          className="group overflow-hidden rounded-xl border border-border/80 bg-card"
                        >
                          <summary className="flex cursor-pointer list-none items-center gap-3 p-3.5 [&::-webkit-details-marker]:hidden">
                            <span
                              className={cn(
                                "grid size-8 shrink-0 place-items-center rounded-xl",
                                tool.is_error
                                  ? "bg-destructive/10 text-destructive"
                                  : "bg-primary/8 text-primary"
                              )}
                            >
                              <Wrench className="size-4" />
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-xs font-semibold">
                                {tool.name || "Tool call"}
                              </p>
                              <p className="text-[10px] text-muted-foreground">
                                {formatDateTime(tool.timestamp)}
                              </p>
                            </div>
                            {tool.is_error && (
                              <Badge variant="destructive">Error</Badge>
                            )}
                            <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
                          </summary>

                          <div className="space-y-3 border-t bg-muted/15 px-3.5 py-3">
                            {tool.arguments != null &&
                            tool.arguments !== "" ? (
                              <div>
                                <p className="text-[10px] font-bold tracking-wide text-muted-foreground uppercase">
                                  Arguments
                                </p>
                                <pre className="mt-1.5 max-h-52 overflow-auto rounded-lg border bg-background p-3 font-mono text-[11px] leading-relaxed break-words whitespace-pre-wrap">
                                  {prettyValue(tool.arguments)}
                                </pre>
                              </div>
                            ) : null}

                            {tool.output != null && tool.output !== "" ? (
                              <div>
                                <p className="text-[10px] font-bold tracking-wide text-muted-foreground uppercase">
                                  Result
                                </p>
                                <pre className="mt-1.5 max-h-52 overflow-auto rounded-lg border bg-background p-3 font-mono text-[11px] leading-relaxed break-words whitespace-pre-wrap">
                                  {prettyValue(tool.output)}
                                </pre>
                              </div>
                            ) : null}

                            {tool.is_error && (
                              <p className="text-xs font-medium text-destructive">
                                This tool reported an error.
                              </p>
                            )}
                          </div>
                        </details>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="latency">
                  {turns.length === 0 ? (
                    <EmptyState
                      icon={Timer}
                      title="No latency samples"
                      description="Timing data is captured when the receptionist speaks."
                      compact
                    />
                  ) : (
                    <div className="space-y-2.5">
                      {turns.map((turn, index) => (
                        <TurnCard
                          key={turn.turn_id || index}
                          turn={turn}
                          index={index}
                        />
                      ))}
                    </div>
                  )}
                </TabsContent>
              </div>
            </Tabs>

            <SheetFooter className="sm:justify-between">
              <p className="hidden text-[11px] text-muted-foreground sm:block">
                Started {formatDateTime(call.started_at)}
              </p>
              <div className="flex w-full gap-2 sm:w-auto">
                {analysisStatus !== "completed" && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => onRetryAnalysis(call.call_id)}
                    disabled={retryingAnalysis}
                    className="flex-1 sm:flex-none"
                  >
                    {retryingAnalysis ? (
                      <Loader2 className="animate-spin" />
                    ) : (
                      <RefreshCw />
                    )}
                    {retryingAnalysis ? "Requeueing..." : "Retry analysis"}
                  </Button>
                )}
                <Button
                  type="button"
                  size="sm"
                  onClick={() => onOpenChange(false)}
                  className="flex-1 sm:flex-none"
                >
                  Close
                </Button>
              </div>
            </SheetFooter>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

export { CallDetailSheet };
