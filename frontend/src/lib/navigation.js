import {
  AudioLines,
  BookOpen,
  CalendarDays,
  Gauge,
  History,
  Stethoscope,
  UsersRound,
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
    id: "doctors",
    to: "/admin/doctors",
    label: "Doctors",
    shortLabel: "Doctors",
    description: "Roster, schedules, and slots",
    icon: UsersRound,
  },
  {
    id: "clinic",
    to: "/admin/clinic",
    label: "Clinic profile",
    shortLabel: "Clinic",
    description: "Contact, hours, services, and holidays",
    icon: Stethoscope,
  },
  {
    id: "knowledge",
    to: "/admin/knowledge",
    label: "Knowledge base",
    shortLabel: "Knowledge",
    description: "Searchable clinic FAQs and documents",
    icon: BookOpen,
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
