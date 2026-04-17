import { SentinelAuthz, IdpConfigs } from "@sentinel-auth/js";

const SENTINEL_URL =
  process.env.NEXT_PUBLIC_SENTINEL_URL || "http://localhost:9003";
const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:9200";
const GOOGLE_CLIENT_ID =
  process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";

/** Lazy singleton — avoids localStorage access during SSR/prerendering. */
let _client: SentinelAuthz | null = null;

export function getAuthzClient(): SentinelAuthz {
  if (!_client) {
    _client = new SentinelAuthz({
      sentinelUrl: SENTINEL_URL,
      // Mint endpoint lives on the demo backend — it holds the Sentinel service
      // key and proxies the POST /authz/resolve call. Browsers never touch the
      // service key; credential issuance stays server-to-server.
      mintEndpoint: `${BACKEND_URL}/auth/mint`,
      idps: {
        google: IdpConfigs.google(GOOGLE_CLIENT_ID),
      },
    });
  }
  return _client;
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  return getAuthzClient().fetchJson<T>(`${BACKEND_URL}${path}`, options);
}
