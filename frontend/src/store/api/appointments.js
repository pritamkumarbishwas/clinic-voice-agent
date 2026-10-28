import { clinicApi } from "./base-api";

const APPOINTMENT_LIST_TAG = { type: "Appointment", id: "LIST" };
const DOCTOR_LIST_TAG = { type: "Doctor", id: "LIST" };

const appointmentsApi = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    listAppointments: build.query({
      query: ({
        page = 1,
        pageSize = 20,
        status,
        doctor,
        date,
      } = {}) => ({
        url: "/api/appointments",
        params: {
          page,
          page_size: pageSize,
          status: status || undefined,
          doctor: doctor || undefined,
          date: date || undefined,
        },
      }),
      providesTags: [APPOINTMENT_LIST_TAG],
    }),
    listDoctors: build.query({
      query: ({ includeInactive = false } = {}) => ({
        url: "/api/doctors",
        params: { include_inactive: includeInactive },
      }),
      providesTags: [DOCTOR_LIST_TAG],
    }),
  }),
  overrideExisting: false,
});

export const {
  useListAppointmentsQuery,
  useListDoctorsQuery,
} = appointmentsApi;
