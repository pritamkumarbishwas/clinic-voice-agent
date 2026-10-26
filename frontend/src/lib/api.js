export const API_URL = (
  import.meta.env.VITE_API_URL || ""
).replace(/\/+$/, "");

export const AUTH_UNAUTHORIZED_EVENT = "clinic:unauthorized";

function notifyUnauthorized() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
  }
}

async function parseResponse(response) {
  if (response.status === 204) return null;

  const text = await response.text();
  let body = null;

  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }

  if (!response.ok) {
    let detail =
      typeof body === "string" && body
        ? body
        : `${response.status} ${response.statusText}`;

    if (body?.detail) {
      detail =
        typeof body.detail === "string"
          ? body.detail
          : JSON.stringify(body.detail);
    }

    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }

  return body;
}

async function request(path, options = {}) {
  const { body, ...rest } = options;
  const response = await fetch(`${API_URL}${path}`, {
    credentials: "include",
    cache: "no-store",
    ...rest,
    headers: {
      Accept: "application/json",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...rest.headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (
    response.status === 401 &&
    !path.startsWith("/api/auth/login")
  ) {
    notifyUnauthorized();
  }

  return parseResponse(response);
}

export async function apiGet(path, { signal, headers } = {}) {
  return request(path, { signal, headers });
}

export async function apiPost(path, body, { signal, headers } = {}) {
  return request(path, { method: "POST", body, signal, headers });
}

export async function apiPut(path, body, { signal, headers } = {}) {
  return request(path, { method: "PUT", body, signal, headers });
}
