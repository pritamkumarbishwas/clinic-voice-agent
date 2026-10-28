import assert from "node:assert/strict";
import test from "node:test";

import {
  cleanClinicProfile,
  emptyHoliday,
  emptyService,
  toClinicProfile,
} from "./clinic-profile.js";

test("toClinicProfile preserves FAQ fields", () => {
  const profile = toClinicProfile({
    name: "Sunrise",
    email: "hello@example.com",
    services: [{ name: "General consultation", fee: "500", description: "Check-up" }],
    appointment_policy: "Arrive early",
    cancellation_policy: "Call staff",
    holidays: [{ date: "2026-11-08", name: "Diwali", closed: true }],
  });

  assert.equal(profile.email, "hello@example.com");
  assert.equal(profile.services.length, 1);
  assert.equal(profile.services[0].fee, "500");
  assert.equal(profile.appointment_policy, "Arrive early");
  assert.equal(profile.cancellation_policy, "Call staff");
  assert.equal(profile.holidays[0].date, "2026-11-08");
});

test("cleanClinicProfile drops empty rows and normalizes text", () => {
  const profile = cleanClinicProfile({
    name: "  Sunrise   Clinic ",
    email: " HELLO@EXAMPLE.COM ",
    hours: { open: "10:00", close: "17:00", days: "  Monday   to Saturday " },
    services: [
      { name: "", fee: "", description: "" },
      { name: " Dental  check-up ", fee: " 700 ", description: " Cleaning " },
    ],
    holidays: [
      { date: "", name: "", closed: true },
      { date: "2026-12-25", name: " Christmas ", closed: true },
    ],
  });

  assert.equal(profile.name, "Sunrise Clinic");
  assert.equal(profile.email, "hello@example.com");
  assert.equal(profile.hours.days, "Monday to Saturday");
  assert.deepEqual(profile.services, [
    { name: "Dental check-up", fee: "700", description: "Cleaning" },
  ]);
  assert.deepEqual(profile.holidays, [
    { date: "2026-12-25", name: "Christmas", closed: true },
  ]);
});

test("empty row factories produce blank valid shapes", () => {
  assert.deepEqual(emptyService(), { name: "", description: "", fee: "" });
  assert.deepEqual(emptyHoliday(), { date: "", name: "", closed: true });
});
