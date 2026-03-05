import { Link, useLocation } from "react-router-dom";
import { useUser } from "./AuthGuard";
import { clearTokens } from "../api/client";
import { RoleBadge } from "./RoleBadge";

export function Layout({ children }: { children: React.ReactNode }) {
  const user = useUser();
  const location = useLocation();

  const navLinks = [
    { to: "/notes", label: "Notes" },
    { to: "/notes/export", label: "Export" },
  ];

  return (
    <div className="min-h-screen bg-zinc-950">
      <nav className="border-b border-zinc-800 bg-zinc-900/50 px-6 py-3">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <div className="flex items-center gap-6">
            <Link to="/notes" className="text-lg font-semibold text-zinc-100">
              Team Notes
            </Link>
            <div className="flex gap-1">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  className={`rounded px-3 py-1.5 text-sm transition ${
                    location.pathname === link.to
                      ? "bg-zinc-700 text-zinc-100"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm text-zinc-300">{user.name}</div>
              <div className="flex items-center gap-2 text-xs text-zinc-500">
                <span>{user.workspace_slug}</span>
                <RoleBadge role={user.workspace_role} />
              </div>
            </div>
            <button
              onClick={() => {
                clearTokens();
                window.location.href = "/";
              }}
              className="rounded bg-zinc-800 px-3 py-1.5 text-xs text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200"
            >
              Logout
            </button>
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-4xl px-6 py-8">{children}</main>
    </div>
  );
}
