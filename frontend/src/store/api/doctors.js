import { clinicApi } from "./base-api";

const DOCTOR_LIST_TAG = { type: "Doctor", id: "LIST" };
const APPOINTMENT_LIST_TAG = { type: "Appointment", id: "LIST" };

const doctorsApi = clinicApi.injectEndpoints({
  endpoints: (build) => ({
    createDoctor: build.mutation({
      query: (doctor) => ({
        url: "/api/doctors",
        method: "POST",
        body: doctor,
      }),
      invalidatesTags: [DOCTOR_LIST_TAG, APPOINTMENT_LIST_TAG],
    }),
    updateDoctor: build.mutation({
      query: ({ doctorId, ...doctor }) => ({
        url: `/api/doctors/${doctorId}`,
        method: "PUT",
        body: doctor,
      }),
      invalidatesTags: [DOCTOR_LIST_TAG, APPOINTMENT_LIST_TAG],
    }),
    deactivateDoctor: build.mutation({
      query: ({ doctorId, cancelFutureAppointments = false }) => ({
        url: `/api/doctors/${doctorId}`,
        method: "DELETE",
        params: { cancel_future: cancelFutureAppointments },
      }),
      invalidatesTags: [DOCTOR_LIST_TAG, APPOINTMENT_LIST_TAG],
    }),
    getDoctorFutureAppointments: build.query({
      query: (doctorId) =>
        `/api/doctors/${doctorId}/future-appointments`,
    }),
    generateDoctorSlots: build.mutation({
      query: ({ doctorId, days = 14 }) => ({
        url: `/api/doctors/${doctorId}/slots`,
        method: "POST",
        params: { days },
      }),
      invalidatesTags: [DOCTOR_LIST_TAG],
    }),
  }),
  overrideExisting: false,
});

export const {
  useCreateDoctorMutation,
  useDeactivateDoctorMutation,
  useGenerateDoctorSlotsMutation,
  useGetDoctorFutureAppointmentsQuery,
  useLazyGetDoctorFutureAppointmentsQuery,
  useUpdateDoctorMutation,
} = doctorsApi;
