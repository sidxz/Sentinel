import { SentinelAuthz, IdpConfigs } from "@sentinel-auth/js";

const SENTINEL_URL =
  import.meta.env.VITE_SENTINEL_URL || "http://localhost:9003";
const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL || "http://localhost:9200";
const GOOGLE_CLIENT_ID =
  import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

/** Shared SentinelAuthz client instance. */
export const authzClient = new SentinelAuthz({
  sentinelUrl: SENTINEL_URL,
  idps: {
    google: IdpConfigs.google(GOOGLE_CLIENT_ID),
  },
});

/**
 * Fetch wrapper for the demo backend API.
 * Uses SentinelAuthz's fetchJson for automatic dual-token injection and 401 retry.
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  return authzClient.fetchJson<T>(`${BACKEND_URL}${path}`, options);
}
