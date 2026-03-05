import { IDENTITY_URL, setTokens } from "./client";

export interface WorkspaceOption {
  id: string;
  name: string;
  slug: string;
  role: string;
}

export function loginWithGoogle() {
  window.location.href = `${IDENTITY_URL}/auth/login/google`;
}

export async function fetchWorkspaces(
  userId: string
): Promise<WorkspaceOption[]> {
  const res = await fetch(
    `${IDENTITY_URL}/auth/workspaces?user_id=${userId}`
  );
  if (!res.ok) throw new Error("Failed to fetch workspaces");
  return res.json();
}

export async function exchangeToken(
  userId: string,
  workspaceId: string
): Promise<void> {
  const res = await fetch(`${IDENTITY_URL}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, workspace_id: workspaceId }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Token exchange failed");
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
}
