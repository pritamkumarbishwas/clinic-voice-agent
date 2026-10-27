import { configureStore } from "@reduxjs/toolkit";
import { setupListeners } from "@reduxjs/toolkit/query";

import { clinicApi } from "./api";
import authReducer from "./slices/auth-slice";

const store = configureStore({
  reducer: {
    auth: authReducer,
    [clinicApi.reducerPath]: clinicApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(clinicApi.middleware),
  devTools: import.meta.env?.DEV ?? false,
});

setupListeners(store.dispatch);

export { store };
