export function emptyService() {
  return { name: "", description: "", fee: "" };
}

export function emptyHoliday() {
  return { date: "", name: "", closed: true };
}

export function toClinicProfile(data) {
  return {
    name: data?.name ?? "",
    address: data?.address ?? "",
    phone: data?.phone ?? "",
    email: data?.email ?? "",
    website: data?.website ?? "",
    hours: {
      open: data?.hours?.open ?? "10:00",
      close: data?.hours?.close ?? "17:00",
      days: data?.hours?.days ?? "Mon-Sat",
    },
    consultation_fee: data?.consultation_fee ?? "",
    services: Array.isArray(data?.services)
      ? data.services.map((service) => ({
          name: service?.name ?? "",
          description: service?.description ?? "",
          fee: service?.fee ?? "",
        }))
      : [],
    appointment_policy: data?.appointment_policy ?? "",
    cancellation_policy: data?.cancellation_policy ?? "",
    holidays: Array.isArray(data?.holidays)
      ? data.holidays.map((holiday) => ({
          date: holiday?.date ?? "",
          name: holiday?.name ?? "",
          closed: holiday?.closed ?? true,
        }))
      : [],
    emergency_note: data?.emergency_note ?? "",
  };
}

function cleanText(value) {
  return `${value ?? ""}`.trim().replace(/\s+/g, " ");
}

function cleanWebsite(value) {
  const cleaned = cleanText(value);
  if (!cleaned || /^https?:\/\//i.test(cleaned)) {
    return cleaned;
  }
  return `https://${cleaned}`;
}

export function cleanClinicProfile(profile) {
  return {
    ...profile,
    name: cleanText(profile?.name),
    address: cleanText(profile?.address),
    phone: cleanText(profile?.phone),
    email: cleanText(profile?.email).toLowerCase(),
    website: cleanWebsite(profile?.website),
    hours: {
      open: profile?.hours?.open ?? "10:00",
      close: profile?.hours?.close ?? "17:00",
      days: cleanText(profile?.hours?.days),
    },
    consultation_fee: cleanText(profile?.consultation_fee),
    services: (profile?.services ?? [])
      .map((service) => ({
        name: cleanText(service?.name),
        description: cleanText(service?.description),
        fee: cleanText(service?.fee),
      }))
      .filter((service) => service.name),
    appointment_policy: cleanText(profile?.appointment_policy),
    cancellation_policy: cleanText(profile?.cancellation_policy),
    holidays: (profile?.holidays ?? [])
      .map((holiday) => ({
        date: cleanText(holiday?.date),
        name: cleanText(holiday?.name),
        closed: holiday?.closed ?? true,
      }))
      .filter((holiday) => holiday.date && holiday.name)
      .sort((left, right) => left.date.localeCompare(right.date)),
    emergency_note: cleanText(profile?.emergency_note),
  };
}
