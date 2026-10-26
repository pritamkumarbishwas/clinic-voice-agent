import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Phone,
  RefreshCw,
  Stethoscope,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { formatDateTime, formatNumber, titleCase } from "@/lib/format";

const STATUS_OPTIONS = ["all", "confirmed", "completed", "cancelled"];

function statusVariant(status) {
  if (status === "confirmed") return "success";
  if (status === "cancelled") return "destructive";
  if (status === "completed") return "secondary";
  return "outline";
}

function AppointmentsSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 5 }).map((_, index) => (
        <div
          key={index}
          className="flex items-center gap-4 rounded-2xl border border-border/80 bg-card px-5 py-4"
        >
          <Skeleton className="size-9 rounded-xl" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-3 w-44" />
            <Skeleton className="h-2.5 w-28" />
          </div>
          <Skeleton className="h-5 w-20 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export default function Appointments() {
  const [appointments, setAppointments] = useState([]);
  const [doctors, setDoctors] = useState([]);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("all");
  const [doctor, setDoctor] = useState("all");
  const [date, setDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    apiGet("/api/doctors", { signal: controller.signal })
      .then((data) => setDoctors(data.items ?? []))
      .catch(() => {
        // Doctor filtering is optional; the table still works without it.
      });

    return () => controller.abort();
  }, [reloadKey]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({
      page: String(page),
      page_size: "20",
    });

    if (status !== "all") params.set("status", status);
    if (doctor !== "all") params.set("doctor", doctor);
    if (date) params.set("date", date);

    apiGet(`/api/appointments?${params.toString()}`, {
      signal: controller.signal,
    })
      .then((data) => {
        setAppointments(data.items ?? []);
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
  }, [page, status, doctor, date, reloadKey]);

  const hasFilters = status !== "all" || doctor !== "all" || date !== "";

  function refresh() {
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  function resetFilters() {
    setLoading(true);
    setPage(1);
    setStatus("all");
    setDoctor("all");
    setDate("");
  }

  function changeFilter(setter, value) {
    setLoading(true);
    setPage(1);
    setter(value);
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <PageHeader
        icon={CalendarDays}
        eyebrow="Appointments"
        title="Patient bookings"
        description="Every appointment the AI receptionist has booked, with doctor, time, and contact details."
        actions={
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={loading}
          >
            <RefreshCw className={loading ? "animate-spin" : undefined} />
            Refresh
          </Button>
        }
      />

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1.5">
            <Label htmlFor="appointment-status">Status</Label>
            <Select
              value={status}
              onValueChange={(value) => changeFilter(setStatus, value)}
            >
              <SelectTrigger id="appointment-status" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option === "all" ? "All statuses" : titleCase(option)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="appointment-doctor">Doctor</Label>
            <Select
              value={doctor}
              onValueChange={(value) => changeFilter(setDoctor, value)}
            >
              <SelectTrigger id="appointment-doctor" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All doctors</SelectItem>
                {doctors.map((item) => (
                  <SelectItem key={item.name} value={item.name}>
                    {item.name}
                    {item.specialty ? ` · ${item.specialty}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="appointment-date">Date</Label>
            <Input
              id="appointment-date"
              type="date"
              value={date}
              onChange={(event) =>
                changeFilter(setDate, event.target.value)
              }
            />
          </div>

          <div className="flex items-end">
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              onClick={resetFilters}
              disabled={!hasFilters}
            >
              Clear filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Could not load appointments</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-2">
            <span>{error}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={refresh}
            >
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {loading ? (
        <AppointmentsSkeleton />
      ) : appointments.length === 0 ? (
        <EmptyState
          icon={CalendarDays}
          title={
            hasFilters
              ? "No appointments match these filters"
              : "No appointments booked yet"
          }
          description={
            hasFilters
              ? "Try clearing one or more filters to see more bookings."
              : "When the AI receptionist confirms a booking, it will appear here."
          }
          action={
            hasFilters ? (
              <Button type="button" variant="outline" onClick={resetFilters}>
                Clear filters
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="hidden overflow-hidden rounded-2xl border border-border/80 bg-card md:block">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  <TableHead className="pl-5">Patient</TableHead>
                  <TableHead>Doctor</TableHead>
                  <TableHead>Appointment</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead className="pr-5 text-right">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {appointments.map((appointment) => (
                  <TableRow key={appointment.appointment_id}>
                    <TableCell className="pl-5">
                      <p className="text-sm font-semibold">
                        {appointment.name}
                      </p>
                      <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                        {appointment.appointment_id}
                      </p>
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1.5 text-xs">
                        <Stethoscope className="size-3.5 text-muted-foreground" />
                        {appointment.doctor_name}
                      </span>
                    </TableCell>
                    <TableCell className="text-xs">
                      {formatDateTime(appointment.start_at)}
                    </TableCell>
                    <TableCell>
                      <a
                        href={`tel:${appointment.phone}`}
                        className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
                      >
                        <Phone className="size-3.5" />
                        {appointment.phone}
                      </a>
                    </TableCell>
                    <TableCell className="pr-5 text-right">
                      <Badge variant={statusVariant(appointment.status)}>
                        {titleCase(appointment.status)}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="space-y-2.5 md:hidden">
            {appointments.map((appointment) => (
              <div
                key={appointment.appointment_id}
                className="rounded-2xl border border-border/80 bg-card p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold">
                      {appointment.name}
                    </p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {appointment.doctor_name}
                    </p>
                  </div>
                  <Badge variant={statusVariant(appointment.status)}>
                    {titleCase(appointment.status)}
                  </Badge>
                </div>

                <div className="mt-3 space-y-1.5 border-t pt-3 text-xs text-muted-foreground">
                  <p>{formatDateTime(appointment.start_at)}</p>
                  <a
                    href={`tel:${appointment.phone}`}
                    className="inline-flex items-center gap-1.5 text-primary"
                  >
                    <Phone className="size-3.5" />
                    {appointment.phone}
                  </a>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col items-center justify-between gap-3 rounded-2xl border border-border/80 bg-card px-4 py-3 sm:flex-row">
            <p className="text-xs text-muted-foreground">
              Page {page} of {pages} · {formatNumber(total)} appointments
            </p>
            <div className="flex w-full gap-2 sm:w-auto">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setLoading(true);
                  setPage((value) => Math.max(1, value - 1));
                }}
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
                onClick={() => {
                  setLoading(true);
                  setPage((value) => Math.min(pages, value + 1));
                }}
                disabled={page >= pages}
                className="flex-1 sm:flex-none"
              >
                Next
                <ChevronRight />
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
