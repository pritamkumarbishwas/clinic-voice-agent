import { useEffect, useRef } from "react";
import { useDispatch, useSelector } from "react-redux";

import { useGetSessionQuery } from "@/store/api";
import {
  selectAuthStatus,
  sessionCleared,
  sessionLoaded,
  sessionLoading,
} from "@/store/slices/auth-slice";

function SessionBootstrap() {
  const dispatch = useDispatch();
  const status = useSelector(selectAuthStatus);
  const bootstrappedRef = useRef(false);
  const { data, isError, isLoading } = useGetSessionQuery();

  useEffect(() => {
    if (bootstrappedRef.current) return;

    if (status !== "loading") {
      bootstrappedRef.current = true;
      return;
    }

    if (isLoading) {
      dispatch(sessionLoading());
      return;
    }

    bootstrappedRef.current = true;

    if (isError) {
      dispatch(sessionCleared());
      return;
    }

    dispatch(sessionLoaded(data?.user ?? null));
  }, [data, dispatch, isError, isLoading, status]);

  return null;
}

export { SessionBootstrap };
