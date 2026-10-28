import assert from "node:assert/strict";
import test from "node:test";

import {
  cleanDoctor,
  emptyDoctor,
  formatWorkingDays,
  toggleWorkingDay,
  toDoctorForm,
} from "./doctors.js";

test("emptyDoctor starts with a valid weekday schedule", () => {
  const doctor = emptyDoctor();

  assert.equal(doctor.name, "");
  assert.deepEqual(doctor.working_days, [0, 1, 2, 3, 4, 5]);
  assert.equal(doctor.slot_minutes, 30);
});

test("toDoctorForm joins languages and preserves schedule", () => {
  const doctor = toDoctorForm({
    doctor_id: "abc",
    name: "Dr. Sharma",
    languages: ["Hindi", "English"],
    working_days: [1, 3],
  });

  assert.equal(doctor.doctor_id, "abc");
  assert.equal(doctor.languagesText, "Hindi, English");
  assert.deepEqual(doctor.working_days, [1, 3]);
});

test("cleanDoctor normalizes languages and schedule", () => {
  const doctor = cleanDoctor({
    name: "  Dr.   Sharma ",
    languagesText: " Hindi, english, Hindi, ",
    working_days: [5, 1, 1],
    slot_minutes: "45",
  });

  assert.equal(doctor.name, "Dr. Sharma");
  assert.deepEqual(doctor.languages, ["Hindi", "english"]);
  assert.deepEqual(doctor.working_days, [1, 5]);
  assert.equal(doctor.slot_minutes, 45);
});

test("formatWorkingDays produces readable labels", () => {
  assert.equal(formatWorkingDays([]), "Not scheduled");
  assert.equal(formatWorkingDays([0, 1, 2, 3, 4, 5, 6]), "Every day");
  assert.equal(formatWorkingDays([0, 2, 6]), "Mon, Wed, Sun");
});

test("toggleWorkingDay adds and removes a day", () => {
  assert.deepEqual(toggleWorkingDay([0, 1], 2), [0, 1, 2]);
  assert.deepEqual(toggleWorkingDay([0, 1], 1), [0]);
});
