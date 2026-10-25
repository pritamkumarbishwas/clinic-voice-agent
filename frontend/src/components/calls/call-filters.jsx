import { RotateCcw, SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

function FilterSelect({ id, label, value, onChange, children }) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id} className="text-[11px] text-muted-foreground">
        {label}
      </Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger id={id} className="w-full bg-background">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>{children}</SelectContent>
      </Select>
    </div>
  );
}

function CallFilters({
  runs,
  runFilter,
  onRunChange,
  outcomeFilter,
  onOutcomeChange,
  sentimentFilter,
  onSentimentChange,
  onReset,
  hasFilters,
}) {
  return (
    <Card>
      <CardContent className="p-4 sm:p-5">
        <div className="mb-3 flex items-center gap-2">
          <SlidersHorizontal className="size-4 text-muted-foreground" />
          <h2 className="text-xs font-bold tracking-wide text-muted-foreground uppercase">
            Filters
          </h2>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-[1.2fr_1fr_1fr_auto] xl:items-end">
          <FilterSelect
            id="run-filter"
            label="Benchmark run"
            value={runFilter}
            onChange={onRunChange}
          >
            <SelectItem value="all">All runs</SelectItem>
            {runs.map((run) => (
              <SelectItem key={run.run_id} value={run.run_id}>
                {run.run_id} ({run.call_count} calls)
              </SelectItem>
            ))}
          </FilterSelect>

          <FilterSelect
            id="outcome-filter"
            label="Booking outcome"
            value={outcomeFilter}
            onChange={onOutcomeChange}
          >
            <SelectItem value="all">All outcomes</SelectItem>
            <SelectItem value="booked">Booked</SelectItem>
            <SelectItem value="not_booked">Not booked</SelectItem>
            <SelectItem value="unknown">Unknown</SelectItem>
          </FilterSelect>

          <FilterSelect
            id="sentiment-filter"
            label="Sentiment"
            value={sentimentFilter}
            onChange={onSentimentChange}
          >
            <SelectItem value="all">All sentiments</SelectItem>
            <SelectItem value="positive">Positive</SelectItem>
            <SelectItem value="neutral">Neutral</SelectItem>
            <SelectItem value="negative">Negative</SelectItem>
            <SelectItem value="unknown">Unknown</SelectItem>
          </FilterSelect>

          <Button
            type="button"
            variant="outline"
            onClick={onReset}
            disabled={!hasFilters}
            className="w-full xl:w-auto"
          >
            <RotateCcw />
            Reset
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export { CallFilters };
