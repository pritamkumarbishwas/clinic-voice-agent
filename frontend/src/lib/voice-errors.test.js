import assert from "node:assert/strict";
import test from "node:test";

import { describeVoiceError, voiceError } from "./voice-errors.js";

test("maps microphone permission denial", () => {
  const result = describeVoiceError(
    { name: "NotAllowedError" },
    "permission"
  );

  assert.equal(result.title, "Microphone access denied");
  assert.match(result.message, /allow microphone access/i);
});

test("maps a missing microphone", () => {
  const result = describeVoiceError(
    { name: "NotFoundError" },
    "microphone"
  );

  assert.equal(result.title, "No microphone found");
});

test("maps a microphone that is already in use", () => {
  const result = describeVoiceError(
    { name: "NotReadableError" },
    "microphone"
  );

  assert.equal(result.title, "Microphone is busy");
});

test("maps an insecure context", () => {
  const result = describeVoiceError(
    voiceError("INSECURE_CONTEXT"),
    "permission"
  );

  assert.equal(result.title, "Microphone unavailable");
  assert.match(result.message, /https or localhost/i);
});

test("maps a token timeout", () => {
  const result = describeVoiceError(voiceError("TOKEN_TIMEOUT"), "token");

  assert.equal(result.title, "Voice service unavailable");
  assert.match(result.message, /did not respond/i);
});

test("maps an agent join timeout", () => {
  const result = describeVoiceError(voiceError("AGENT_TIMEOUT"), "agent");

  assert.equal(result.title, "Receptionist unavailable");
  assert.match(result.message, /agent worker/i);
});

test("maps rate limiting", () => {
  const error = Object.assign(new Error("rate limited"), { status: 429 });
  const result = describeVoiceError(error, "token");

  assert.equal(result.title, "Too many call attempts");
});

test("maps token service failures", () => {
  const error = Object.assign(new Error("server error"), { status: 503 });
  const result = describeVoiceError(error, "token");

  assert.equal(result.title, "Voice service unavailable");
});

test("maps a network failure", () => {
  const result = describeVoiceError(new TypeError("Failed to fetch"), "token");

  assert.equal(result.title, "Voice service unavailable");
  assert.match(result.message, /check your connection/i);
});

test("maps a LiveKit unreachable server", () => {
  const error = Object.assign(new Error("unreachable"), {
    name: "ConnectionError",
    reasonName: "ServerUnreachable",
  });
  const result = describeVoiceError(error, "connection");

  assert.equal(result.title, "Voice connection failed");
  assert.match(result.message, /voice server/i);
});

test("preserves the voice error code and cause", () => {
  const cause = new Error("cause");
  const error = voiceError("MIC_UNAVAILABLE", cause);

  assert.equal(error.code, "MIC_UNAVAILABLE");
  assert.equal(error.cause, cause);
});
