import { AudioLines, Gauge, History } from "lucide-react";

export const NAV_ITEMS = [
  {
    id: "live",
    label: "Live call",
    shortLabel: "Live",
    description: "Start and monitor a voice session",
    icon: AudioLines,
  },
  {
    id: "calls",
    label: "Call log",
    shortLabel: "Calls",
    description: "Review conversations and outcomes",
    icon: History,
  },
  {
    id: "latency",
    label: "Latency",
    shortLabel: "Latency",
    description: "Inspect speech and response timings",
    icon: Gauge,
  },
];

export function getNavItem(id) {
  return NAV_ITEMS.find((item) => item.id === id) || NAV_ITEMS[0];
}
