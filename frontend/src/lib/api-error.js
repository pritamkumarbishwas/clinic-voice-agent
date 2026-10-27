const DEFAULT_ERROR_MESSAGE = "Something went wrong";

function stringifyDetail(detail) {
  if (typeof detail === "string") return detail;
  if (detail == null) return "";

  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

function getApiErrorMessage(error, fallback = DEFAULT_ERROR_MESSAGE) {
  if (!error) return fallback;

  const data = error.data;
  const detail = data?.detail ?? data?.message;

  if (detail != null) {
    return stringifyDetail(detail) || fallback;
  }

  if (typeof data === "string") {
    return data || fallback;
  }

  if (typeof error.error === "string") {
    return error.error || fallback;
  }

  if (typeof error.message === "string") {
    return error.message || fallback;
  }

  return fallback;
}

export { getApiErrorMessage };
