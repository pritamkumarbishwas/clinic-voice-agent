import {
  CheckCircle2,
  CircleDashed,
  Clock3,
  Loader2,
  MinusCircle,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { titleCase } from "@/lib/format";

function OutcomeBadge({ outcome }) {
  if (outcome === "booked") {
    return (
      <Badge variant="success">
        <CheckCircle2 />
        Booked
      </Badge>
    );
  }

  if (outcome === "not_booked") {
    return (
      <Badge variant="secondary">
        <MinusCircle />
        Not booked
      </Badge>
    );
  }

  return (
    <Badge variant="outline">
      <CircleDashed />
      {titleCase(outcome)}
    </Badge>
  );
}

function SentimentBadge({ sentiment }) {
  if (sentiment === "positive") {
    return (
      <Badge variant="success">
        <ThumbsUp />
        Positive
      </Badge>
    );
  }

  if (sentiment === "negative") {
    return (
      <Badge variant="destructive">
        <ThumbsDown />
        Negative
      </Badge>
    );
  }

  if (sentiment === "neutral") {
    return (
      <Badge variant="secondary">
        <CircleDashed />
        Neutral
      </Badge>
    );
  }

  return (
    <Badge variant="outline">
      <CircleDashed />
      {titleCase(sentiment)}
    </Badge>
  );
}

function AnalysisBadge({ status }) {
  if (status === "completed") {
    return (
      <Badge variant="success">
        <Sparkles />
        Analyzed
      </Badge>
    );
  }

  if (status === "running") {
    return (
      <Badge variant="info">
        <Loader2 className="animate-spin" />
        Analyzing
      </Badge>
    );
  }

  if (status === "failed") {
    return (
      <Badge variant="destructive">
        <TriangleAlert />
        Failed
      </Badge>
    );
  }

  return (
    <Badge variant="outline">
      <Clock3 />
      {status === "pending" ? "Pending" : titleCase(status)}
    </Badge>
  );
}

export { AnalysisBadge, OutcomeBadge, SentimentBadge };
