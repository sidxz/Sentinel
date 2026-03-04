import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getUserDetail, updateUser } from "../api/client";
import { RoleBadge, StatusBadge } from "../components/Badge";

export function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const { data: user, isLoading } = useQuery({
    queryKey: ["user", id],
    queryFn: () => getUserDetail(id!),
    enabled: !!id,
  });

  const toggleActive = useMutation({
    mutationFn: () => updateUser(id!, { is_active: !user?.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["user", id] }),
  });

  if (isLoading) return <div className="animate-pulse h-64 bg-zinc-800/30 rounded-lg" />;
  if (!user) return <div className="text-zinc-500">User not found</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <Link to="/users" className="hover:text-zinc-300">Users</Link>
        <span>/</span>
        <span className="text-zinc-200">{user.name}</span>
      </div>

      {/* Profile card */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex items-start gap-4">
          <div className="w-14 h-14 rounded-full bg-zinc-700 flex items-center justify-center text-xl font-semibold text-zinc-300 shrink-0">
            {user.name.charAt(0).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-lg font-semibold">{user.name}</h2>
            <div className="text-sm text-zinc-400 mt-0.5">{user.email}</div>
            <div className="flex items-center gap-3 mt-2">
              <StatusBadge active={user.is_active} />
              <span className="text-xs text-zinc-500">
                Joined {new Date(user.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
          <button
            onClick={() => toggleActive.mutate()}
            disabled={toggleActive.isPending}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
              user.is_active
                ? "bg-red-500/10 text-red-400 hover:bg-red-500/20 ring-1 ring-red-500/20"
                : "bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 ring-1 ring-emerald-500/20"
            }`}
          >
            {user.is_active ? "Deactivate" : "Activate"}
          </button>
        </div>
      </div>

      {/* Social accounts */}
      {user.social_accounts.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-zinc-400 mb-2">Linked Accounts</h3>
          <div className="flex gap-2">
            {user.social_accounts.map((sa) => (
              <div
                key={sa.id}
                className="px-3 py-2 rounded-md border border-zinc-800 bg-zinc-900 text-sm"
              >
                <span className="font-medium capitalize">{sa.provider}</span>
                <span className="text-zinc-500 ml-2 text-xs">{sa.provider_user_id}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Workspace memberships */}
      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-2">
          Workspaces ({user.memberships.length})
        </h3>
        {user.memberships.length === 0 ? (
          <div className="text-sm text-zinc-500 py-4">No workspace memberships</div>
        ) : (
          <div className="rounded-lg border border-zinc-800 divide-y divide-zinc-800/50">
            {user.memberships.map((m) => (
              <Link
                key={m.workspace_id}
                to={`/workspaces/${m.workspace_id}`}
                className="flex items-center justify-between px-4 py-3 hover:bg-zinc-800/40 transition-colors"
              >
                <div>
                  <div className="text-sm font-medium">{m.workspace_name}</div>
                  <div className="text-xs text-zinc-500">{m.workspace_slug}</div>
                </div>
                <div className="flex items-center gap-3">
                  <RoleBadge role={m.role} />
                  <span className="text-xs text-zinc-500">
                    {new Date(m.joined_at).toLocaleDateString()}
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
