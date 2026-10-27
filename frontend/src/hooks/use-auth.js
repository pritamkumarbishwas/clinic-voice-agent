import { useCallback, useMemo } from "react";
import { useDispatch, useSelector } from "react-redux";

import {
  clinicApi,
  useLoginMutation,
  useLogoutMutation,
} from "@/store/api";
import {
  selectAuthLoading,
  selectAuthUser,
  sessionCleared,
  sessionLoaded,
} from "@/store/slices/auth-slice";

function useAuth() {
  const dispatch = useDispatch();
  const user = useSelector(selectAuthUser);
  const loading = useSelector(selectAuthLoading);
  const [loginMutation] = useLoginMutation();
  const [logoutMutation] = useLogoutMutation();

  const login = useCallback(
    async (email, password) => {
      const data = await loginMutation({ email, password }).unwrap();
      const nextUser = data?.user ?? null;

      dispatch(sessionLoaded(nextUser));
      if (nextUser) {
        void dispatch(
          clinicApi.util.upsertQueryData("getSession", undefined, data)
        );
      }

      return nextUser;
    },
    [dispatch, loginMutation]
  );

  const logout = useCallback(async () => {
    try {
      await logoutMutation().unwrap();
    } catch {
      // Local sign-out still succeeds when the server is unreachable.
    } finally {
      dispatch(sessionCleared());
      dispatch(clinicApi.util.resetApiState());
    }
  }, [dispatch, logoutMutation]);

  return useMemo(
    () => ({ user, loading, login, logout }),
    [loading, login, logout, user]
  );
}

export { useAuth };
