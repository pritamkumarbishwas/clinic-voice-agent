import assert from "node:assert/strict";
import test from "node:test";

import {
  authSlice,
  sessionCleared,
  sessionLoaded,
  sessionLoading,
} from "./auth-slice.js";

const initialState = authSlice.reducer(undefined, { type: "@@init" });

test("starts in the loading state", () => {
  assert.deepEqual(initialState, { user: null, status: "loading" });
});

test("stores an authenticated session", () => {
  const state = authSlice.reducer(
    initialState,
    sessionLoaded({ id: "1", email: "admin@clinic.test" })
  );

  assert.equal(state.status, "authenticated");
  assert.equal(state.user.email, "admin@clinic.test");
});

test("treats a null session as anonymous", () => {
  const state = authSlice.reducer(
    authSlice.reducer(initialState, sessionLoading()),
    sessionLoaded(null)
  );

  assert.deepEqual(state, { user: null, status: "anonymous" });
});

test("clears the session", () => {
  const authenticated = authSlice.reducer(
    initialState,
    sessionLoaded({ id: "1" })
  );
  const state = authSlice.reducer(authenticated, sessionCleared());

  assert.deepEqual(state, { user: null, status: "anonymous" });
});
