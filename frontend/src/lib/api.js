export const API_URL = (
  import.meta.env.VITE_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export async function apiGet(path, { signal } = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    signal,
    headers: { Accept: "application/json" },
  });

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
