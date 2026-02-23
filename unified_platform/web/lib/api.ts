// Server-side (SSR/Server Components): use internal Docker hostname for reliability.
// Client-side (browser): falls back to NEXT_PUBLIC_API_BASE_URL.
const _rawPublic = process.env.NEXT_PUBLIC_API_BASE_URL || "";
const _rawInternal = process.env.API_INTERNAL_URL || "";

export const API_BASE_URL: string = (() => {
  // Pick the right base depending on execution context
  const url = (typeof window === "undefined" ? _rawInternal || _rawPublic : _rawPublic) ||
    "http://localhost:8080";
  // Ensure there is a scheme so fetch() doesn't throw
  if (url && !url.startsWith("http://") && !url.startsWith("https://")) {
    return `https://${url}`;
  }
  return url;
})();

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    cache: "no-store"
  });
  return parseJson<T>(response);
}

export async function apiPost<T>(path: string, body: unknown, token?: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(body),
    cache: "no-store"
  });
  return parseJson<T>(response);
}
