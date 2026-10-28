import {
  CalendarPlus,
  Check,
  Loader2,
  Pencil,
  Plus,
  Power,
  RefreshCw,
  Search,
  Stethoscope,
  TriangleAlert,
  UserRoundCheck,
  X,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  DAY_LABELS,
  cleanDoctor,
  emptyDoctor,
  formatWorkingDays,
  toDoctorForm,
  toggleWorkingDay,
} from "@/lib/doctors";
import {
  useCreateDoctorMutation,
  useDeactivateDoctorMutation,
  useGenerateDoctorSlotsMutation,
  useLazyGetDoctorFutureAppointmentsQuery,
  useListDoctorsQuery,
  useUpdateDoctorMutation,
} from "@/store/api";

const TEXTAREA_CLASS =
  "w-full rounded-lg border border-input bg-background/70 px-3 py-2 text-sm shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25";

function DoctorForm({ initial, onCancel, onSaved }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState("");
  const [createDoctor, { isLoading: creating }] = useCreateDoctorMutation();
  const [updateDoctor, { isLoading: updating }] = useUpdateDoctorMutation();
  const saving = creating || updating;
  const isEditing = Boolean(initial.doctor_id);

  function setField(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");

    const payload = cleanDoctor(form);
    if (payload.name.length < 2) {
      setError("Doctor name must be at least 2 characters.");
      return;
    }
    if (payload.working_days.length === 0) {
      setError("Select at least one working day.");
      return;
    }
    if (payload.start_time >= payload.end_time) {
      setError("End time must be after start time.");
      return;
    }

    try {
      if (isEditing) {
        await updateDoctor({
          doctorId: initial.doctor_id,
          ...payload,
        }).unwrap();
        toast.success("Doctor updated");
      } else {
        await createDoctor(payload).unwrap();
        toast.success("Doctor added");
      }
      onSaved();
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not save the doctor"));
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {error && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Could not save doctor</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="doctor-name">Name</Label>
              <Input
                id="doctor-name"
                value={form.name}
                onChange={(event) => setField("name", event.target.value)}
                maxLength={120}
                placeholder="Dr. Anjali Sharma"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="doctor-specialty">Specialty</Label>
              <Input
                id="doctor-specialty"
                value={form.specialty}
                onChange={(event) =>
                  setField("specialty", event.target.value)
                }
                maxLength={120}
                placeholder="General physician"
              />
            </div>

            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="doctor-languages">
                Languages, separated by commas
              </Label>
              <Input
                id="doctor-languages"
                value={form.languagesText}
                onChange={(event) =>
                  setField("languagesText", event.target.value)
                }
                placeholder="Hindi, English"
              />
            </div>

            <div className="space-y-1.5 sm:col-span-2">
              <Label htmlFor="doctor-bio">
                Bio for clinic knowledge search
              </Label>
              <textarea
                id="doctor-bio"
                value={form.bio}
                onChange={(event) => setField("bio", event.target.value)}
                maxLength={3000}
                rows={3}
                className={TEXTAREA_CLASS}
                placeholder="Experience, focus areas, and other clinic-relevant details."
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Working days</Label>
            <div className="flex flex-wrap gap-2">
              {DAY_LABELS.map((label, day) => {
                const selected = form.working_days.includes(day);
                return (
                  <Button
                    key={label}
                    type="button"
                    size="sm"
                    variant={selected ? "default" : "outline"}
                    onClick={() =>
                      setField(
                        "working_days",
                        toggleWorkingDay(form.working_days, day)
                      )
                    }
                  >
                    {selected && <Check />}
                    {label}
                  </Button>
                );
              })}
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="doctor-start">Start time</Label>
              <Input
                id="doctor-start"
                type="time"
                value={form.start_time}
                onChange={(event) =>
                  setField("start_time", event.target.value)
                }
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="doctor-end">End time</Label>
              <Input
                id="doctor-end"
                type="time"
                value={form.end_time}
                onChange={(event) => setField("end_time", event.target.value)}
                required
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="doctor-slot">Slot length (minutes)</Label>
              <Input
                id="doctor-slot"
                type="number"
                min={10}
                max={120}
                step={5}
                value={form.slot_minutes}
                onChange={(event) =>
                  setField("slot_minutes", event.target.value)
                }
                required
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={form.active}
              onChange={(event) => setField("active", event.target.checked)}
              className="size-4 rounded border-input accent-primary"
            />
            Active and bookable
          </label>

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              type="button"
              variant="ghost"
              onClick={onCancel}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="animate-spin" />}
              {saving
                ? "Saving..."
                : isEditing
                  ? "Save doctor"
                  : "Add doctor"}
            </Button>
      </div>
    </form>
  );
}

export default function Doctors() {
  const [formState, setFormState] = useState(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [pendingDeactivate, setPendingDeactivate] = useState(null);
  const [deactivatingId, setDeactivatingId] = useState("");
  const doctorsQuery = useListDoctorsQuery({ includeInactive: true });
  const { currentData, isError, isFetching, isLoading, refetch } =
    doctorsQuery;
  const [getFutureAppointments] =
    useLazyGetDoctorFutureAppointmentsQuery();
  const [deactivateDoctor, { isLoading: deactivating }] =
    useDeactivateDoctorMutation();
  const [generateSlots, { isLoading: generating }] =
    useGenerateDoctorSlotsMutation();
  const [updateDoctor] = useUpdateDoctorMutation();

  const doctors = currentData?.items ?? [];
  const activeCount = doctors.filter((doctor) => doctor.active).length;
  const inactiveCount = doctors.length - activeCount;
  const searchTerm = query.trim().toLocaleLowerCase();
  const filteredDoctors = doctors.filter((doctor) => {
    if (statusFilter === "active" && !doctor.active) return false;
    if (statusFilter === "inactive" && doctor.active) return false;
    if (!searchTerm) return true;
    return [doctor.name, doctor.specialty, ...(doctor.languages ?? [])]
      .filter(Boolean)
      .some((value) =>
        value.toLocaleLowerCase().includes(searchTerm)
      );
  });
  const loadError = isError
    ? getApiErrorMessage(doctorsQuery.error, "Could not load doctors")
    : "";

  async function requestDeactivate(doctor) {
    setDeactivatingId(doctor.doctor_id);
    try {
      const result = await getFutureAppointments(
        doctor.doctor_id
      ).unwrap();
      setPendingDeactivate({ doctor, count: result.count ?? 0 });
    } catch (err) {
      toast.error(
        getApiErrorMessage(err, "Could not check future appointments")
      );
    } finally {
      setDeactivatingId("");
    }
  }

  async function confirmDeactivate(cancelFutureAppointments) {
    if (!pendingDeactivate) return;

    try {
      const result = await deactivateDoctor({
        doctorId: pendingDeactivate.doctor.doctor_id,
        cancelFutureAppointments,
      }).unwrap();
      toast.success(
        cancelFutureAppointments
          ? `Doctor deactivated and ${result.cancelled_appointments} appointment(s) cancelled`
          : "Doctor deactivated"
      );
      setPendingDeactivate(null);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Could not deactivate doctor"));
    }
  }

  async function handleReactivate(doctor) {
    try {
      const payload = {
        ...cleanDoctor(toDoctorForm(doctor)),
        active: true,
      };
      await updateDoctor({
        doctorId: doctor.doctor_id,
        ...payload,
      }).unwrap();
      toast.success("Doctor reactivated");
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Could not reactivate doctor"));
    }
  }

  async function handleGenerateSlots(doctor) {
    try {
      const result = await generateSlots({
        doctorId: doctor.doctor_id,
        days: 14,
      }).unwrap();
      toast.success(`${result.created} slot(s) ready for the next 14 days`);
    } catch (err) {
      toast.error(getApiErrorMessage(err, "Could not generate slots"));
    }
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <PageHeader
        icon={Stethoscope}
        eyebrow="Doctors"
        title="Doctor directory"
        description="Manage the doctors the receptionist may offer, their weekly schedule, and bookable slots."
        actions={
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={isFetching ? "animate-spin" : ""} />
              Refresh
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => setFormState(emptyDoctor())}
            >
              <Plus />
              Add doctor
            </Button>
          </div>
        }
      />

      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
        <Badge variant="success">{activeCount} active</Badge>
        <Badge variant="secondary">{inactiveCount} inactive</Badge>
        <span>
          {doctors.length} doctor{doctors.length === 1 ? "" : "s"} total
        </span>
      </div>

      {doctors.length > 0 && (
        <div className="flex flex-col gap-2 rounded-2xl border border-border/80 bg-card p-2 shadow-xs sm:flex-row sm:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search doctors, specialties, or languages"
              className="border-0 bg-transparent pl-9 shadow-none focus-visible:ring-0"
              aria-label="Search doctors"
            />
          </div>
          <div className="flex shrink-0 gap-1 rounded-xl bg-muted p-1">
            {[
              ["all", "All"],
              ["active", "Active"],
              ["inactive", "Inactive"],
            ].map(([value, label]) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={statusFilter === value ? "default" : "ghost"}
                onClick={() => setStatusFilter(value)}
                className="h-7 flex-1 sm:flex-none"
              >
                {label}
              </Button>
            ))}
          </div>
        </div>
      )}

      {pendingDeactivate && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>
            Deactivate {pendingDeactivate.doctor.name}?
          </AlertTitle>
          <AlertDescription className="space-y-3">
            <p>
              The doctor will no longer be offered to callers.{" "}
              {pendingDeactivate.count > 0
                ? `${pendingDeactivate.count} future appointment(s) are still confirmed.`
                : "There are no future appointments."}
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => confirmDeactivate(false)}
                disabled={deactivating}
              >
                {deactivating && <Loader2 className="animate-spin" />}
                Deactivate only
              </Button>
              {pendingDeactivate.count > 0 && (
                <Button
                  type="button"
                  variant="destructive"
                  size="sm"
                  onClick={() => confirmDeactivate(true)}
                  disabled={deactivating}
                >
                  {deactivating && <Loader2 className="animate-spin" />}
                  Deactivate and cancel appointments
                </Button>
              )}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setPendingDeactivate(null)}
                disabled={deactivating}
              >
                <X />
                Keep active
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {formState && (
        <Sheet
          open
          onOpenChange={(open) => {
            if (!open) setFormState(null);
          }}
        >
          <SheetContent className="sm:max-w-xl">
            <SheetHeader>
              <SheetTitle>
                {formState.doctor_id ? "Edit doctor" : "Add a doctor"}
              </SheetTitle>
              <SheetDescription>
                The receptionist only offers doctors who are active and
                scheduled. Bio text is searchable by the knowledge assistant.
              </SheetDescription>
            </SheetHeader>
            <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-7">
              <DoctorForm
                key={formState.doctor_id || "new"}
                initial={formState}
                onCancel={() => setFormState(null)}
                onSaved={() => setFormState(null)}
              />
            </div>
          </SheetContent>
        </Sheet>
      )}

      {loadError && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Could not load doctors</AlertTitle>
          <AlertDescription className="flex flex-col items-start gap-2">
            <span>{loadError}</span>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isFetching}
            >
              <RefreshCw className={isFetching ? "animate-spin" : ""} />
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-28 rounded-2xl" />
          ))}
        </div>
      ) : doctors.length === 0 ? (
        <EmptyState
          icon={Stethoscope}
          title="No doctors yet"
          description="Add the first doctor so the receptionist can offer appointments."
          action={
            <Button
              type="button"
              size="sm"
              onClick={() => setFormState(emptyDoctor())}
            >
              <Plus />
              Add doctor
            </Button>
          }
        />
      ) : filteredDoctors.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No matching doctors"
          description="Try a different name, specialty, or status filter."
          action={
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setQuery("");
                setStatusFilter("all");
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <div className="space-y-3">
          {filteredDoctors.map((doctor) => (
            <Card key={doctor.doctor_id}>
              <CardContent className="flex flex-col gap-4 py-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-bold">{doctor.name}</h3>
                    <Badge variant={doctor.active ? "success" : "secondary"}>
                      {doctor.active ? "Active" : "Inactive"}
                    </Badge>
                    {doctor.specialty && (
                      <span className="text-xs text-muted-foreground">
                        {doctor.specialty}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {formatWorkingDays(doctor.working_days)} ·{" "}
                    {doctor.start_time}-{doctor.end_time} ·{" "}
                    {doctor.slot_minutes} min slots
                  </p>
                  {doctor.languages.length > 0 && (
                    <p className="text-xs text-muted-foreground">
                      Languages: {doctor.languages.join(", ")}
                    </p>
                  )}
                  {doctor.bio && (
                    <p className="line-clamp-2 max-w-2xl text-xs text-muted-foreground">
                      {doctor.bio}
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleGenerateSlots(doctor)}
                    disabled={!doctor.active || generating}
                  >
                    <CalendarPlus />
                    Generate slots
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setFormState(toDoctorForm(doctor))}
                  >
                    <Pencil />
                    Edit
                  </Button>
                  {doctor.active ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => requestDeactivate(doctor)}
                      disabled={deactivatingId === doctor.doctor_id}
                    >
                      {deactivatingId === doctor.doctor_id ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <Power />
                      )}
                      Deactivate
                    </Button>
                  ) : (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => handleReactivate(doctor)}
                    >
                      <UserRoundCheck />
                      Reactivate
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
