import { IDENTITY_URL, setTokens } from "./client";

const REDIRECT_URI = `${window.location.origin}/auth/callback`;

export interface WorkspaceOption {
  id: string;
  name: string;
  slug: string;
  role: string;
}

export function loginWithGoogle() {
  const params = new URLSearchParams({
    redirect_uri: REDIRECT_URI,
  });
  window.location.href = `${IDENTITY_URL}/auth/login/google?${params}`;
}

export async function fetchWorkspaces(
  code: string
): Promise<WorkspaceOption[]> {
  const res = await fetch(
    `${IDENTITY_URL}/auth/workspaces?code=${encodeURIComponent(code)}`
  );
  if (!res.ok) throw new Error("Failed to fetch workspaces");
  return res.json();
}

export async function exchangeToken(
  code: string,
  workspaceId: string
): Promise<void> {
  const res = await fetch(`${IDENTITY_URL}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, workspace_id: workspaceId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Token exchange failed");
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
}
