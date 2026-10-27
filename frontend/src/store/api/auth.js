import { clinicApi } from "./base-api";

const authApi = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    getSession: build.query({
      query: () => "/api/auth/me",
      providesTags: ["Session"],
      keepUnusedDataFor: 300,
    }),
    login: build.mutation({
      query: (credentials) => ({
        url: "/api/auth/login",
        method: "POST",
        body: credentials,
      }),
    }),
    logout: build.mutation({
      query: () => ({
        url: "/api/auth/logout",
        method: "POST",
      }),
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetSessionQuery,
  useLoginMutation,
  useLogoutMutation,
} = authApi;
