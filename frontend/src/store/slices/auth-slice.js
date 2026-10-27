import { createSlice } from "@reduxjs/toolkit";

const initialState = {
  user: null,
  status: "loading",
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    sessionLoading(state) {
      state.status = "loading";
    },
    sessionLoaded(state, action) {
      const user = action.payload ?? null;
      state.user = user;
      state.status = user ? "authenticated" : "anonymous";
    },
    sessionCleared(state) {
      state.user = null;
      state.status = "anonymous";
    },
  },
});

const { sessionCleared, sessionLoaded, sessionLoading } =
  authSlice.actions;

const selectAuthUser = (state) => state.auth.user;
const selectAuthStatus = (state) => state.auth.status;
const selectAuthLoading = (state) => state.auth.status === "loading";

export {
  authSlice,
  selectAuthLoading,
  selectAuthStatus,
  selectAuthUser,
  sessionCleared,
  sessionLoaded,
  sessionLoading,
};

export default authSlice.reducer;
