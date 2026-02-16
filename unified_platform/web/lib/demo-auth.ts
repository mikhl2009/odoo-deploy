import { API_BASE_URL } from "./api";

let cachedToken: string | null = null;

export async function getDemoToken(): Promise<string | null> {
  if (cachedToken) {
    return cachedToken;
  }
  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "admin@unified.local", password: "admin123" }),
      cache: "no-store"
    });
    if (!response.ok) {
      return null;
    }
    const data = (await response.json()) as { access_token: string };
    cachedToken = data.access_token;
    return cachedToken;
  } catch {
    return null;
  }
}
