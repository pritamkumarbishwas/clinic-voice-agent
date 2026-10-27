import { clinicApi } from "./base-api";

const clinicApiSlice = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    getClinic: build.query({
      query: () => "/api/clinic",
      providesTags: ["Clinic"],
    }),
    updateClinic: build.mutation({
      query: (profile) => ({
        url: "/api/clinic",
        method: "PUT",
        body: profile,
      }),
      invalidatesTags: ["Clinic"],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetClinicQuery,
  useUpdateClinicMutation,
} = clinicApiSlice;
