import assert from "node:assert/strict";
import test from "node:test";

import { getApiErrorMessage } from "./api-error.js";

test("uses the backend detail message", () => {
  assert.equal(
    getApiErrorMessage({ status: 400, data: { detail: "Bad date" } }),
    "Bad date"
  );
});

test("stringifies structured backend details", () => {
  assert.equal(
    getApiErrorMessage({
      status: 422,
      data: { detail: [{ field: "email", message: "Invalid" }] },
    }),
    '[{"field":"email","message":"Invalid"}]'
  );
});

test("falls back to a plain response body", () => {
  assert.equal(
    getApiErrorMessage({ status: 500, data: "Server unavailable" }),
    "Server unavailable"
  );
});

test("handles fetch errors", () => {
  assert.equal(
    getApiErrorMessage({
      status: "FETCH_ERROR",
      error: "TypeError: Failed to fetch",
    }),
    "TypeError: Failed to fetch"
  );
});

test("uses the provided fallback for missing errors", () => {
  assert.equal(getApiErrorMessage(null, "Could not load"), "Could not load");
});
