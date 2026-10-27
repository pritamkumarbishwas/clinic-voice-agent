import { clinicApi } from "./base-api";

const healthApi = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    getHealth: build.query({
      query: () => "/api/health",
    }),
  }),
  overrideExisting: false,
});

export const { useGetHealthQuery } = healthApi;
