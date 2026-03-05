import { loginWithGoogle } from "../api/auth";

export function Login() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-950">
      <div className="w-full max-w-sm space-y-6 text-center">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Team Notes</h1>
          <p className="mt-1 text-sm text-zinc-500">
            Daikon Identity SDK Demo
          </p>
        </div>

        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <p className="mb-4 text-sm text-zinc-400">
            Sign in to manage workspace notes. This app demonstrates
            authentication, workspace roles, RBAC actions, and entity-level
            permissions.
          </p>
          <button
            onClick={loginWithGoogle}
            className="w-full rounded bg-white px-4 py-2.5 text-sm font-medium text-zinc-900 hover:bg-zinc-200 transition"
          >
            Sign in with Google
          </button>
        </div>

        <div className="space-y-2 text-xs text-zinc-600">
          <p>Powered by Daikon Identity Service</p>
          <div className="flex justify-center gap-4">
            <span>JWT Auth</span>
            <span>&middot;</span>
            <span>Workspace Roles</span>
            <span>&middot;</span>
            <span>RBAC</span>
            <span>&middot;</span>
            <span>Entity ACLs</span>
          </div>
        </div>
      </div>
    </div>
  );
}
