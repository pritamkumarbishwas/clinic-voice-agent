import { clinicApi } from "./base-api";

const analyticsApi = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    listRuns: build.query({
      query: () => "/api/analytics/runs",
      providesTags: [{ type: "Run", id: "LIST" }],
    }),
    getLatency: build.query({
      query: ({ runId } = {}) => ({
        url: "/api/analytics/latency",
        params:
          runId && runId !== "all"
            ? { run_id: runId }
            : undefined,
      }),
      providesTags: (_result, _error, { runId } = {}) => [
        { type: "Latency", id: runId || "all" },
      ],
    }),
  }),
  overrideExisting: false,
});

export const {
  useListRunsQuery,
  useGetLatencyQuery,
} = analyticsApi;
