import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getStats } from "../api/client";
import { StatusBadge } from "../components/Badge";

export function Dashboard() {
  const { data, isLoading, error } = useQuery({ queryKey: ["stats"], queryFn: getStats });

  if (isLoading) return <Skeleton />;
  if (error) return <ErrorState message={(error as Error).message} />;
  if (!data) return null;

  const cards = [
    { label: "Users", value: data.total_users, href: "/users" },
    { label: "Workspaces", value: data.total_workspaces, href: "/workspaces" },
    { label: "Groups", value: data.total_groups, href: "/workspaces" },
    { label: "Resources", value: data.total_resources, href: "/permissions" },
  ];

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Dashboard</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-4 gap-4">
        {cards.map((c) => (
          <Link
            key={c.label}
            to={c.href}
            className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 hover:border-zinc-700 transition-colors"
          >
            <div className="text-2xl font-bold tabular-nums">{c.value}</div>
            <div className="text-xs text-zinc-500 mt-1">{c.label}</div>
          </Link>
        ))}
      </div>

      {/* Recent users */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-zinc-400">Recent Users</h2>
          <Link to="/users" className="text-xs text-zinc-500 hover:text-zinc-300">
            View all &rarr;
          </Link>
        </div>
        <div className="rounded-lg border border-zinc-800 divide-y divide-zinc-800/50">
          {data.recent_users.map((u) => (
            <Link
              key={u.id}
              to={`/users/${u.id}`}
              className="flex items-center gap-3 px-4 py-3 hover:bg-zinc-800/40 transition-colors"
            >
              <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center text-xs font-medium text-zinc-300 shrink-0">
                {u.name.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium truncate">{u.name}</div>
                <div className="text-xs text-zinc-500 truncate">{u.email}</div>
              </div>
              <StatusBadge active={u.is_active} />
              <div className="text-xs text-zinc-500 tabular-nums">
                {u.workspace_count} workspace{u.workspace_count !== 1 ? "s" : ""}
              </div>
            </Link>
          ))}
          {data.recent_users.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-zinc-500">No users yet</div>
          )}
        </div>
      </div>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="space-y-8 animate-pulse">
      <div className="h-6 w-32 bg-zinc-800 rounded" />
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-20 bg-zinc-800 rounded-lg" />
        ))}
      </div>
      <div className="h-48 bg-zinc-800 rounded-lg" />
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-6 text-center">
      <div className="text-sm text-red-400">Failed to load dashboard</div>
      <div className="text-xs text-red-500/70 mt-1">{message}</div>
    </div>
  );
}
