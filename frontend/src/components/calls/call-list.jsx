import { ChevronRight, Hand, PhoneCall } from "lucide-react";

import {
  AnalysisBadge,
  OutcomeBadge,
  SentimentBadge,
} from "@/components/shared/status-badge";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatCallDuration, formatDateTime } from "@/lib/format";

function CallList({ calls, onOpenCall }) {
  function handleKeyDown(event, callId) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onOpenCall(callId);
    }
  }

  return (
    <>
      <div className="hidden overflow-hidden rounded-2xl border border-border/80 bg-card shadow-[0_18px_50px_-42px_rgba(15,23,42,0.5)] md:block">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/30 hover:bg-muted/30">
              <TableHead className="pl-5">Call</TableHead>
              <TableHead>Outcome</TableHead>
              <TableHead>Sentiment</TableHead>
              <TableHead>Analysis</TableHead>
              <TableHead className="text-right">Duration</TableHead>
              <TableHead className="text-right">Barge-ins</TableHead>
              <TableHead className="w-10 pr-5" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {calls.map((call) => (
              <TableRow
                key={call.call_id}
                role="button"
                tabIndex={0}
                aria-label={`Open call ${call.call_id}`}
                onClick={() => onOpenCall(call.call_id)}
                onKeyDown={(event) => handleKeyDown(event, call.call_id)}
                className="cursor-pointer focus-visible:bg-accent/50 focus-visible:outline-none"
              >
                <TableCell className="max-w-[22rem] pl-5">
                  <div className="flex items-center gap-3">
                    <span className="grid size-9 shrink-0 place-items-center rounded-xl border border-primary/12 bg-primary/8 text-primary">
                      <PhoneCall className="size-4" />
                    </span>
                    <div className="min-w-0">
                      <p
                        className="truncate font-mono text-xs font-semibold"
                        title={call.call_id}
                      >
                        {call.call_id}
                      </p>
                      <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                        <span>{formatDateTime(call.started_at)}</span>
                        {call.run_id && (
                          <Badge variant="outline" className="text-[9px]">
                            {call.run_id}
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <OutcomeBadge outcome={call.booking_outcome} />
                </TableCell>
                <TableCell>
                  <SentimentBadge sentiment={call.sentiment} />
                </TableCell>
                <TableCell>
                  <AnalysisBadge status={call.analysis_status} />
                </TableCell>
                <TableCell className="text-right text-xs text-muted-foreground">
                  {formatCallDuration(call)}
                </TableCell>
                <TableCell className="text-right">
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                    <Hand className="size-3.5" />
                    {call.barge_in_count ?? 0}
                  </span>
                </TableCell>
                <TableCell className="pr-5 text-right">
                  <ChevronRight className="ml-auto size-4 text-muted-foreground/60" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="space-y-2.5 md:hidden">
        {calls.map((call) => (
          <button
            key={call.call_id}
            type="button"
            onClick={() => onOpenCall(call.call_id)}
            className="w-full rounded-2xl border border-border/80 bg-card p-4 text-left shadow-xs transition-colors hover:bg-muted/20 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2.5">
                <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-primary/8 text-primary">
                  <PhoneCall className="size-4" />
                </span>
                <div className="min-w-0">
                  <p
                    className="truncate font-mono text-xs font-semibold"
                    title={call.call_id}
                  >
                    {call.call_id}
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">
                    {formatDateTime(call.started_at)}
                  </p>
                </div>
              </div>
              <ChevronRight className="size-4 shrink-0 text-muted-foreground/60" />
            </div>

            <div className="mt-3 flex flex-wrap gap-1.5">
              <OutcomeBadge outcome={call.booking_outcome} />
              <SentimentBadge sentiment={call.sentiment} />
              <AnalysisBadge status={call.analysis_status} />
            </div>

            <div className="mt-3 flex items-center justify-between border-t pt-2.5 text-[11px] text-muted-foreground">
              <span>{formatCallDuration(call)}</span>
              <span className="inline-flex items-center gap-1">
                <Hand className="size-3.5" />
                {call.barge_in_count ?? 0} barge-ins
              </span>
              {call.run_id && <span className="truncate">{call.run_id}</span>}
            </div>
          </button>
        ))}
      </div>
    </>
  );
}

function CallListSkeleton() {
  return (
    <div className="space-y-3">
      <div className="hidden overflow-hidden rounded-2xl border bg-card md:block">
        <div className="border-b bg-muted/30 px-5 py-4">
          <Skeleton className="h-3 w-40" />
        </div>
        {Array.from({ length: 5 }).map((_, index) => (
          <div
            key={index}
            className="flex items-center gap-4 border-b px-5 py-4 last:border-0"
          >
            <Skeleton className="size-9 rounded-xl" />
            <div className="flex-1 space-y-2">
              <Skeleton className="h-3 w-48 max-w-full" />
              <Skeleton className="h-2.5 w-32" />
            </div>
            <Skeleton className="h-5 w-20 rounded-full" />
            <Skeleton className="h-5 w-20 rounded-full" />
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
      </div>

      <div className="space-y-2.5 md:hidden">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="rounded-2xl border bg-card p-4">
            <div className="flex items-center gap-3">
              <Skeleton className="size-9 rounded-xl" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-3 w-40 max-w-full" />
                <Skeleton className="h-2.5 w-28" />
              </div>
            </div>
            <div className="mt-3 flex gap-1.5">
              <Skeleton className="h-5 w-20 rounded-full" />
              <Skeleton className="h-5 w-20 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export { CallList, CallListSkeleton };
