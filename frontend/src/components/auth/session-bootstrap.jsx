import { useEffect } from "react";
import { useDispatch } from "react-redux";

import { useGetSessionQuery } from "@/store/api";
import {
  sessionCleared,
  sessionLoaded,
  sessionLoading,
} from "@/store/slices/auth-slice";

function SessionBootstrap() {
  const dispatch = useDispatch();
  const { data, isError, isLoading } = useGetSessionQuery();

  useEffect(() => {
    if (isLoading) {
      dispatch(sessionLoading());
      return;
    }

    if (isError) {
      dispatch(sessionCleared());
      return;
    }

    dispatch(sessionLoaded(data?.user ?? null));
  }, [data, dispatch, isError, isLoading]);

  return null;
}

export { SessionBootstrap };
