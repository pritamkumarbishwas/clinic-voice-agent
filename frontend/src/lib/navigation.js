import {
  AudioLines,
  CalendarDays,
  Gauge,
  History,
  Stethoscope,
} from "lucide-react";

export const NAV_ITEMS = [
  {
    id: "live",
    to: "/admin/live",
    label: "Live call",
    shortLabel: "Live",
    description: "Start and monitor a voice session",
    icon: AudioLines,
  },
  {
    id: "appointments",
    to: "/admin/appointments",
    label: "Appointments",
    shortLabel: "Bookings",
    description: "Confirmed patient bookings",
    icon: CalendarDays,
  },
  {
    id: "calls",
    to: "/admin/calls",
    label: "Call log",
    shortLabel: "Calls",
    description: "Outcomes and transcripts",
    icon: History,
  },
  {
    id: "clinic",
    to: "/admin/clinic",
    label: "Clinic profile",
    shortLabel: "Clinic",
    description: "Contact, hours, and fees",
    icon: Stethoscope,
  },
  {
    id: "latency",
    to: "/admin/latency",
    label: "Latency",
    shortLabel: "Latency",
    description: "Speech and response timings",
    icon: Gauge,
  },
];

export function getNavItem(pathname) {
  return (
    NAV_ITEMS.find(
      (item) =>
        pathname === item.to || pathname.startsWith(`${item.to}/`)
    ) || NAV_ITEMS[0]
  );
}
