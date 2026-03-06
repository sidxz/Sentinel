import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth, type WorkspaceOption } from "@sentinel-auth/react";
import { RoleBadge } from "../components/RoleBadge";

export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { getWorkspaces, selectWorkspace } = useAuth();
  const code = searchParams.get("code");

  const [workspaces, setWorkspaces] = useState<WorkspaceOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!code) {
      setError("Missing authorization code in callback URL");
      setLoading(false);
      return;
    }

    getWorkspaces(code)
      .then(async (ws) => {
        if (ws.length === 0) {
          setError("No workspaces found. Ask an admin to invite you.");
          setLoading(false);
          return;
        }
        if (ws.length === 1) {
          await selectWorkspace(code, ws[0].id);
          navigate("/notes", { replace: true });
          return;
        }
        setWorkspaces(ws);
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load workspaces");
        setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  async function handleSelect(workspaceId: string) {
    if (!code) return;
    setLoading(true);
    try {
      await selectWorkspace(code, workspaceId);
      navigate("/notes", { replace: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Token exchange failed");
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950">
        <div className="text-center">
          <div className="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-zinc-600 border-t-zinc-300" />
          <p className="text-sm text-zinc-500">Signing you in...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950">
        <div className="max-w-sm text-center">
          <p className="mb-4 text-sm text-red-400">{error}</p>
          <a
            href="/"
            className="text-sm text-zinc-400 underline hover:text-zinc-200"
          >
            Back to login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen items-center justify-center bg-zinc-950">
      <div className="w-full max-w-sm">
        <h2 className="mb-4 text-center text-lg font-semibold text-zinc-100">
          Select Workspace
        </h2>
        <div className="space-y-2">
          {workspaces.map((ws) => (
            <button
              key={ws.id}
              onClick={() => handleSelect(ws.id)}
              className="w-full rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-left transition hover:border-zinc-700"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium text-zinc-100">{ws.name}</div>
                  <div className="text-xs text-zinc-500">{ws.slug}</div>
                </div>
                <RoleBadge role={ws.role} />
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
