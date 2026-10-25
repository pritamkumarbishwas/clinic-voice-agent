export const API_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

async function parseResponse(response) {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;

    try {
      const body = await response.json();
      if (body?.detail) {
        detail =
          typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
      }
    } catch {
      // Keep the HTTP status text when the body is not JSON.
    }

    throw new Error(detail);
  }

  return response.json();
}

export async function apiGet(path, { signal } = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    signal,
    cache: "no-store",
    headers: { Accept: "application/json" },
  });

  return parseResponse(response);
}

export async function apiPost(path, body, { signal } = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    signal,
    cache: "no-store",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  return parseResponse(response);
}
