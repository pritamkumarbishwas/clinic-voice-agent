import { clinicApi } from "./base-api";

const liveApi = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    requestToken: build.mutation({
      query: ({ runId } = {}) => ({
        url: "/api/generate-token",
        params: runId ? { run_id: runId } : undefined,
      }),
    }),
  }),
  overrideExisting: false,
});

export const { useRequestTokenMutation } = liveApi;
