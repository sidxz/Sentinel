import { SentinelAuth } from "@sentinel-auth/js";

const SENTINEL_URL =
  import.meta.env.VITE_SENTINEL_URL || "http://localhost:9003";

/** Shared SentinelAuth client instance used by both the React provider and apiFetch. */
export const sentinelClient = new SentinelAuth({
  sentinelUrl: SENTINEL_URL,
});

/**
 * Fetch wrapper for the demo backend API.
 * Uses SentinelAuth's fetch for automatic Bearer token injection and 401 retry.
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string>) ?? {}),
  };

  const res = await sentinelClient.fetch(`/api${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    sentinelClient.logout();
    window.location.href = "/";
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
