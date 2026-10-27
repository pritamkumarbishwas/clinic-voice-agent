import { clinicApi } from "./base-api";

const CALL_LIST_TAG = { type: "Call", id: "LIST" };

const callsApi = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    listCalls: build.query({
      query: ({
        page = 1,
        pageSize = 20,
        runId,
        outcome,
        sentiment,
      } = {}) => ({
        url: "/api/calls",
        params: {
          page,
          page_size: pageSize,
          run_id: runId || undefined,
          outcome: outcome || undefined,
          sentiment: sentiment || undefined,
        },
      }),
      providesTags: [CALL_LIST_TAG],
    }),
    getCall: build.query({
      query: (callId) => `/api/calls/${encodeURIComponent(callId)}`,
      providesTags: (_result, _error, callId) => [
        { type: "Call", id: callId },
      ],
    }),
    requeueAnalysis: build.mutation({
      query: (callId) => ({
        url: `/api/calls/${encodeURIComponent(callId)}/analyze`,
        method: "POST",
      }),
      invalidatesTags: (_result, _error, callId) => [
        { type: "Call", id: callId },
        CALL_LIST_TAG,
      ],
    }),
  }),
  overrideExisting: false,
});

export const {
  useListCallsQuery,
  useGetCallQuery,
  useRequeueAnalysisMutation,
} = callsApi;
