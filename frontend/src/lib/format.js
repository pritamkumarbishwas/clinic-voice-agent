const dateTimeFormatter = new Intl.DateTimeFormat("en-IN", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const timeFormatter = new Intl.DateTimeFormat("en-IN", {
  hour: "2-digit",
  minute: "2-digit",
});

const numberFormatter = new Intl.NumberFormat("en-IN");

function toDate(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatWithUpperPeriod(formatter, date) {
  return formatter
    .format(date)
    .replace(/\b(am|pm)\b/gi, (period) => period.toUpperCase());
}

export function formatDateTime(value) {
  const date = toDate(value);
  return date ? formatWithUpperPeriod(dateTimeFormatter, date) : "n/a";
}

export function formatTime(value) {
  const date = toDate(value);
  return date ? formatWithUpperPeriod(timeFormatter, date) : "n/a";
}

export function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0s";

  const whole = Math.round(seconds);
  const minutes = Math.floor(whole / 60);
  const remaining = whole % 60;

  if (minutes === 0) return `${remaining}s`;
  return `${minutes}m ${remaining}s`;
}

export function formatCallDuration(call) {
  if (!call?.started_at) return "n/a";
  if (!call.ended_at) return "In progress";

  const start = toDate(call.started_at);
  const end = toDate(call.ended_at);
  if (!start || !end) return "n/a";

  return formatDuration((end.getTime() - start.getTime()) / 1000);
}

export function formatMs(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  return `${numberFormatter.format(Math.round(value))} ms`;
}

export function formatNumber(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "0";
  return numberFormatter.format(value);
}

export function formatPercent(value, digits = 0) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}

export function titleCase(value) {
  if (!value) return "Unknown";

  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function pluralize(count, singular, plural) {
  return count === 1 ? singular : plural || `${singular}s`;
}

export function truncate(value, length = 42) {
  if (!value) return "";
  return value.length > length ? `${value.slice(0, length)}...` : value;
}

export function getInitials(value) {
  return String(value || "AI")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
