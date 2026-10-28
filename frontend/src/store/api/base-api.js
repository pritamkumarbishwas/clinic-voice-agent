import {
  createApi,
  fetchBaseQuery,
} from "@reduxjs/toolkit/query/react";

import { sessionCleared } from "../slices/auth-slice";

export const API_URL = (
  import.meta.env?.VITE_API_URL || ""
).replace(/\/+$/, "");

const SESSION_ENDPOINTS = ["/api/auth/login", "/api/auth/me"];

function requestUrl(args) {
  return typeof args === "string" ? args : args?.url ?? "";
}

function isSessionEndpoint(args) {
  const url = requestUrl(args);
  return SESSION_ENDPOINTS.some((path) => url.startsWith(path));
}

function noStoreFetch(input, init) {
  return fetch(input, { ...init, cache: "no-store" });
}

const rawBaseQuery = fetchBaseQuery({
  baseUrl: API_URL,
  credentials: "include",
  fetchFn: noStoreFetch,
  prepareHeaders(headers) {
    headers.set("Accept", "application/json");
    return headers;
  },
});

async function baseQueryWithSession(args, api, extraOptions) {
  const result = await rawBaseQuery(args, api, extraOptions);

  if (result.error?.status === 401 && !isSessionEndpoint(args)) {
    const wasAuthenticated = api.getState().auth?.status === "authenticated";

    api.dispatch(sessionCleared());
    if (wasAuthenticated) {
      api.dispatch(clinicApi.util.resetApiState());
    }
  }

  return result;
}

export const clinicApi = createApi({
  reducerPath: "clinicApi",
  baseQuery: baseQueryWithSession,
  tagTypes: [
    "Session",
    "Call",
    "Appointment",
    "Doctor",
    "Clinic",
    "Knowledge",
    "Run",
    "Latency",
  ],
  endpoints: () => ({}),
});
