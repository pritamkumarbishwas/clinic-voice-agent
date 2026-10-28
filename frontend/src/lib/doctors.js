export const DAY_LABELS = [
  "Mon",
  "Tue",
  "Wed",
  "Thu",
  "Fri",
  "Sat",
  "Sun",
];

export const DEFAULT_WORKING_DAYS = [0, 1, 2, 3, 4, 5];

export function emptyDoctor() {
  return {
    doctor_id: "",
    name: "",
    specialty: "",
    active: true,
    bio: "",
    languagesText: "",
    working_days: [...DEFAULT_WORKING_DAYS],
    start_time: "10:00",
    end_time: "17:00",
    slot_minutes: 30,
  };
}

export function toDoctorForm(data) {
  return {
    doctor_id: data?.doctor_id ?? "",
    name: data?.name ?? "",
    specialty: data?.specialty ?? "",
    active: data?.active ?? true,
    bio: data?.bio ?? "",
    languagesText: Array.isArray(data?.languages)
      ? data.languages.join(", ")
      : "",
    working_days: Array.isArray(data?.working_days)
      ? [...data.working_days]
      : [...DEFAULT_WORKING_DAYS],
    start_time: data?.start_time ?? "10:00",
    end_time: data?.end_time ?? "17:00",
    slot_minutes: data?.slot_minutes ?? 30,
  };
}

export function cleanDoctor(form) {
  const languages = [];
  const seen = new Set();

  for (const part of `${form?.languagesText ?? ""}`.split(",")) {
    const label = part.trim().replace(/\s+/g, " ");
    const key = label.toLocaleLowerCase();
    if (label && !seen.has(key)) {
      seen.add(key);
      languages.push(label);
    }
  }

  return {
    name: `${form?.name ?? ""}`.trim().replace(/\s+/g, " "),
    specialty: `${form?.specialty ?? ""}`.trim().replace(/\s+/g, " "),
    active: form?.active ?? true,
    bio: `${form?.bio ?? ""}`.trim(),
    languages,
    working_days: [...new Set(form?.working_days ?? [])].sort(
      (left, right) => left - right
    ),
    start_time: form?.start_time ?? "10:00",
    end_time: form?.end_time ?? "17:00",
    slot_minutes: Number(form?.slot_minutes ?? 30),
  };
}

export function formatWorkingDays(days) {
  if (!Array.isArray(days) || days.length === 0) {
    return "Not scheduled";
  }
  if (days.length === 7) {
    return "Every day";
  }
  return days
    .map((day) => DAY_LABELS[day])
    .filter(Boolean)
    .join(", ");
}

export function toggleWorkingDay(days, day) {
  const selected = new Set(days);
  if (selected.has(day)) {
    selected.delete(day);
  } else {
    selected.add(day);
  }
  return [...selected].sort((left, right) => left - right);
}
