import { Loader2, Save, Stethoscope, TriangleAlert } from "lucide-react";
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
  useGetClinicQuery,
  useUpdateClinicMutation,
} from "@/store/api";

function toProfile(data) {
  return {
    name: data?.name ?? "",
    address: data?.address ?? "",
    phone: data?.phone ?? "",
    hours: {
      open: data?.hours?.open ?? "10:00",
      close: data?.hours?.close ?? "17:00",
      days: data?.hours?.days ?? "Mon-Sat",
    },
    consultation_fee: data?.consultation_fee ?? "",
    emergency_note: data?.emergency_note ?? "",
  };
}

function ClinicProfileForm({ initialProfile }) {
  const [profile, setProfile] = useState(initialProfile);
  const [savedProfile, setSavedProfile] = useState(initialProfile);
  const [saveError, setSaveError] = useState("");
  const [updateClinic, { isLoading: saving }] =
    useUpdateClinicMutation();

  function setField(field, value) {
    setProfile((previous) => ({ ...previous, [field]: value }));
  }

  function setHours(field, value) {
    setProfile((previous) => ({
      ...previous,
      hours: { ...previous.hours, [field]: value },
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
      const saved = await updateClinic(profile).unwrap();
      const savedValues = toProfile(saved);

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

      <form onSubmit={handleSubmit}>
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
                <Label htmlFor="clinic-fee">Consultation fee</Label>
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
                  maxLength={80}
                  placeholder="Monday to Saturday"
                />
              </div>

              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="clinic-emergency">Emergency note</Label>
                <textarea
                  id="clinic-emergency"
                  value={profile.emergency_note}
                  onChange={(event) =>
                    setField("emergency_note", event.target.value)
                  }
                  maxLength={300}
                  rows={3}
                  className="w-full rounded-lg border border-input bg-background/70 px-3 py-2 text-sm shadow-xs outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/25"
                  placeholder="For emergencies, call 108."
                />
              </div>
            </div>

            <div className="flex flex-col-reverse gap-2 border-t pt-4 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="ghost"
                onClick={resetProfile}
                disabled={saving}
              >
                Reset
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? <Loader2 className="animate-spin" /> : <Save />}
                {saving ? "Saving..." : "Save clinic profile"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
    </>
  );
}

export default function ClinicSettings() {
  const { currentData, isError, isLoading, error } = useGetClinicQuery();
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
        title="Clinic details and FAQ"
        description="The AI receptionist uses these details to answer questions about timings, location, phone, and fees. If a field is empty, it will say staff will confirm."
      />

      {loadError && (
        <Alert variant="destructive">
          <TriangleAlert />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{loadError}</AlertDescription>
        </Alert>
      )}

      <ClinicProfileForm initialProfile={toProfile(currentData)} />
    </div>
  );
}
