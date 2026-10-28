import {
  Loader2,
  Plus,
  RefreshCw,
  Save,
  Stethoscope,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/page-header";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { getApiErrorMessage } from "@/lib/api-error";
import {
  cleanClinicProfile,
  emptyHoliday,
  emptyService,
  toClinicProfile,
} from "@/lib/clinic-profile";
import {
  useGetClinicQuery,
  useUpdateClinicMutation,
} from "@/store/api";

const TEXTAREA_CLASS =
  "w-full rounded-lg border border-input bg-background/70 px-3 py-2 text-sm shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25";

function ClinicProfileForm({ initialProfile }) {
  const [profile, setProfile] = useState(initialProfile);
  const [savedProfile, setSavedProfile] = useState(initialProfile);
  const [saveError, setSaveError] = useState("");
  const [updateClinic, { isLoading: saving }] =
    useUpdateClinicMutation();
  const isDirty = JSON.stringify(profile) !== JSON.stringify(savedProfile);

  function setField(field, value) {
    setProfile((previous) => ({ ...previous, [field]: value }));
  }

  function setHours(field, value) {
    setProfile((previous) => ({
      ...previous,
      hours: { ...previous.hours, [field]: value },
    }));
  }

  function setService(index, field, value) {
    setProfile((previous) => ({
      ...previous,
      services: previous.services.map((service, serviceIndex) =>
        serviceIndex === index
          ? { ...service, [field]: value }
          : service
      ),
    }));
  }

  function addService() {
    setProfile((previous) => ({
      ...previous,
      services: [...previous.services, emptyService()],
    }));
  }

  function removeService(index) {
    setProfile((previous) => ({
      ...previous,
      services: previous.services.filter(
        (_, serviceIndex) => serviceIndex !== index
      ),
    }));
  }

  function setHoliday(index, field, value) {
    setProfile((previous) => ({
      ...previous,
      holidays: previous.holidays.map((holiday, holidayIndex) =>
        holidayIndex === index
          ? { ...holiday, [field]: value }
          : holiday
      ),
    }));
  }

  function addHoliday() {
    setProfile((previous) => ({
      ...previous,
      holidays: [...previous.holidays, emptyHoliday()],
    }));
  }

  function removeHoliday(index) {
    setProfile((previous) => ({
      ...previous,
      holidays: previous.holidays.filter(
        (_, holidayIndex) => holidayIndex !== index
      ),
    }));
  }

  function resetProfile() {
    setSaveError("");
    setProfile(savedProfile);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaveError("");

    try {
      const saved = await updateClinic(
        cleanClinicProfile(profile)
      ).unwrap();
      const savedValues = toClinicProfile(saved);

      setProfile(savedValues);
      setSavedProfile(savedValues);
      toast.success("Clinic profile saved");
    } catch (err) {
      setSaveError(
        getApiErrorMessage(err, "Could not save the clinic profile")
      );
    }
  }

  return (
    <>
      {saveError && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{saveError}</AlertDescription>
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Clinic information</CardTitle>
            <CardDescription>
              Keep this up to date so the receptionist gives accurate answers.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="clinic-name">Clinic name</Label>
                <Input
                  id="clinic-name"
                  value={profile.name}
                  onChange={(event) => setField("name", event.target.value)}
                  maxLength={200}
                  required
                />
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="clinic-address">Address</Label>
                <Input
                  id="clinic-address"
                  value={profile.address}
                  onChange={(event) =>
                    setField("address", event.target.value)
                  }
                  maxLength={500}
                  placeholder="Street, area, city, PIN"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="clinic-phone">Phone</Label>
                <Input
                  id="clinic-phone"
                  value={profile.phone}
                  onChange={(event) => setField("phone", event.target.value)}
                  maxLength={40}
                  placeholder="+91 80 4123 4567"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="clinic-email">Email</Label>
                <Input
                  id="clinic-email"
                  type="email"
                  value={profile.email}
                  onChange={(event) => setField("email", event.target.value)}
                  maxLength={254}
                  placeholder="reception@clinic.example"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="clinic-website">Website</Label>
                <Input
                  id="clinic-website"
                  type="text"
                  inputMode="url"
                  value={profile.website}
                  onChange={(event) =>
                    setField("website", event.target.value)
                  }
                  maxLength={300}
                  placeholder="https://clinic.example"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="clinic-fee">General consultation fee</Label>
                <Input
                  id="clinic-fee"
                  value={profile.consultation_fee}
                  onChange={(event) =>
                    setField("consultation_fee", event.target.value)
                  }
                  maxLength={120}
                  placeholder="500 rupees"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="clinic-open">Opening time</Label>
                <Input
                  id="clinic-open"
                  type="time"
                  value={profile.hours.open}
                  onChange={(event) => setHours("open", event.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="clinic-close">Closing time</Label>
                <Input
                  id="clinic-close"
                  type="time"
                  value={profile.hours.close}
                  onChange={(event) => setHours("close", event.target.value)}
                  required
                />
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="clinic-days">Days open</Label>
                <Input
                  id="clinic-days"
                  value={profile.hours.days}
                  onChange={(event) => setHours("days", event.target.value)}
                  maxLength={120}
                  placeholder="Monday to Saturday"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base">Services and fees</CardTitle>
              <CardDescription>
                The receptionist uses this list for service questions. Leave
                the fee blank to use the general consultation fee.
              </CardDescription>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={addService}>
              <Plus />
              Add service
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {profile.services.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No services configured yet.
              </p>
            ) : (
              profile.services.map((service, index) => (
                <div
                  key={index}
                  className="grid gap-3 rounded-xl border border-border/70 p-3 sm:grid-cols-[1.2fr_0.7fr_1.5fr_auto]"
                >
                  <div className="space-y-1.5">
                    <Label htmlFor={`service-name-${index}`}>Service</Label>
                    <Input
                      id={`service-name-${index}`}
                      value={service.name}
                      onChange={(event) =>
                        setService(index, "name", event.target.value)
                      }
                      maxLength={120}
                      placeholder="General consultation"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`service-fee-${index}`}>Fee</Label>
                    <Input
                      id={`service-fee-${index}`}
                      value={service.fee}
                      onChange={(event) =>
                        setService(index, "fee", event.target.value)
                      }
                      maxLength={120}
                      placeholder="500 rupees"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`service-desc-${index}`}>Description</Label>
                    <Input
                      id={`service-desc-${index}`}
                      value={service.description}
                      onChange={(event) =>
                        setService(index, "description", event.target.value)
                      }
                      maxLength={300}
                      placeholder="Fever, cough, and routine check-ups"
                    />
                  </div>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeService(index)}
                      aria-label="Remove service"
                      title="Remove service"
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Policies</CardTitle>
            <CardDescription>
              These are informational. The receptionist cannot cancel or
              change appointments.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="clinic-appointment-policy">
                Appointment policy
              </Label>
              <textarea
                id="clinic-appointment-policy"
                value={profile.appointment_policy}
                onChange={(event) =>
                  setField("appointment_policy", event.target.value)
                }
                maxLength={1000}
                rows={3}
                className={TEXTAREA_CLASS}
                placeholder="Arrive 10 minutes early and bring previous prescriptions."
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="clinic-cancellation-policy">
                Cancellation policy
              </Label>
              <textarea
                id="clinic-cancellation-policy"
                value={profile.cancellation_policy}
                onChange={(event) =>
                  setField("cancellation_policy", event.target.value)
                }
                maxLength={1000}
                rows={3}
                className={TEXTAREA_CLASS}
                placeholder="Inform clinic staff at least 24 hours before cancelling."
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-start justify-between gap-4">
            <div>
              <CardTitle className="text-base">Holiday closures</CardTitle>
              <CardDescription>
                Closed holiday dates are blocked for new bookings.
              </CardDescription>
            </div>
            <Button type="button" variant="outline" size="sm" onClick={addHoliday}>
              <Plus />
              Add holiday
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            {profile.holidays.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No holiday closures configured.
              </p>
            ) : (
              profile.holidays.map((holiday, index) => (
                <div
                  key={index}
                  className="grid gap-3 rounded-xl border border-border/70 p-3 sm:grid-cols-[0.8fr_1.4fr_auto_auto]"
                >
                  <div className="space-y-1.5">
                    <Label htmlFor={`holiday-date-${index}`}>Date</Label>
                    <Input
                      id={`holiday-date-${index}`}
                      type="date"
                      value={holiday.date}
                      onChange={(event) =>
                        setHoliday(index, "date", event.target.value)
                      }
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor={`holiday-name-${index}`}>Holiday</Label>
                    <Input
                      id={`holiday-name-${index}`}
                      value={holiday.name}
                      onChange={(event) =>
                        setHoliday(index, "name", event.target.value)
                      }
                      maxLength={120}
                      placeholder="Diwali"
                    />
                  </div>
                  <div className="flex items-end pb-2">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={holiday.closed}
                        onChange={(event) =>
                          setHoliday(index, "closed", event.target.checked)
                        }
                        className="size-4 rounded border-input accent-primary"
                      />
                      Closed
                    </label>
                  </div>
                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => removeHoliday(index)}
                      aria-label="Remove holiday"
                      title="Remove holiday"
                    >
                      <Trash2 />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Emergency note</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-1.5">
              <Label htmlFor="clinic-emergency">Emergency note</Label>
              <textarea
                id="clinic-emergency"
                value={profile.emergency_note}
                onChange={(event) =>
                  setField("emergency_note", event.target.value)
                }
                maxLength={300}
                rows={3}
                className={TEXTAREA_CLASS}
                placeholder="For emergencies, call 108."
              />
            </div>
          </CardContent>
        </Card>

        <div className="sticky bottom-20 z-10 flex flex-col gap-3 rounded-2xl border border-border/80 bg-background/92 p-3 shadow-lg backdrop-blur-xl sm:flex-row sm:items-center sm:justify-between lg:bottom-4">
          <div className="flex items-center gap-2 px-1 text-xs font-medium text-muted-foreground">
            <span
              className={`size-2 rounded-full ${
                isDirty ? "bg-warning" : "bg-success"
              }`}
              aria-hidden="true"
            />
            {isDirty
              ? "You have unsaved changes"
              : "All changes are saved"}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row">
            <Button
              type="button"
              variant="ghost"
              onClick={resetProfile}
              disabled={saving || !isDirty}
            >
              Discard changes
            </Button>
            <Button type="submit" disabled={saving || !isDirty}>
              {saving ? <Loader2 className="animate-spin" /> : <Save />}
              {saving ? "Saving..." : "Save changes"}
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}

export default function ClinicSettings() {
  const {
    currentData,
    isError,
    isFetching,
    isLoading,
    error,
    refetch,
  } = useGetClinicQuery();
  const loadError = isError
    ? getApiErrorMessage(error, "Could not load the clinic profile")
    : "";

  if (isLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-96 rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-up">
      <PageHeader
        icon={Stethoscope}
        eyebrow="Clinic profile"
        title="Clinic details"
        description="The AI receptionist uses these details for timings, contact, services, fees, policies, and holidays. Empty fields are answered with staff confirmation."
      />

      {isError || !currentData ? (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Clinic profile unavailable</AlertTitle>
          <AlertDescription>
            {loadError || "Could not load the clinic profile."} The form is
            disabled until the saved profile loads.
          </AlertDescription>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="col-start-2 justify-self-start"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={isFetching ? "animate-spin" : ""} />
            {isFetching ? "Retrying..." : "Try again"}
          </Button>
        </Alert>
      ) : (
        <ClinicProfileForm initialProfile={toClinicProfile(currentData)} />
      )}
    </div>
  );
}
