import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { addUserToWorkspace, getAllWorkspaces, getUserDetail, revokeUserTokens, updateUser } from "../api/client";
import { RoleBadge, StatusBadge } from "../components/Badge";
import { ConfirmModal } from "../components/ConfirmModal";
import { Modal } from "../components/Modal";

export function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [showConfirmToggle, setShowConfirmToggle] = useState(false);
  const [showConfirmAdmin, setShowConfirmAdmin] = useState(false);
  const [showConfirmRevoke, setShowConfirmRevoke] = useState(false);
  const [showAddWorkspace, setShowAddWorkspace] = useState(false);
  const [addWsId, setAddWsId] = useState("");
  const [addWsRole, setAddWsRole] = useState("viewer");

  const { data: user, isLoading } = useQuery({
    queryKey: ["user", id],
    queryFn: () => getUserDetail(id!),
    enabled: !!id,
  });

  const { data: allWorkspaces = [] } = useQuery({
    queryKey: ["all-workspaces"],
    queryFn: getAllWorkspaces,
    enabled: showAddWorkspace,
  });

  const updateName = useMutation({
    mutationFn: () => updateUser(id!, { name: nameValue }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", id] });
      setEditingName(false);
    },
  });

  const toggleActive = useMutation({
    mutationFn: () => updateUser(id!, { is_active: !user?.is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", id] });
      setShowConfirmToggle(false);
    },
  });

  const toggleAdmin = useMutation({
    mutationFn: () => updateUser(id!, { is_admin: !user?.is_admin }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", id] });
      setShowConfirmAdmin(false);
    },
  });

  const revokeTokens = useMutation({
    mutationFn: () => revokeUserTokens(id!),
    onSuccess: () => {
      setShowConfirmRevoke(false);
    },
  });

  const addToWorkspace = useMutation({
    mutationFn: () => addUserToWorkspace(id!, addWsId, addWsRole),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user", id] });
      setShowAddWorkspace(false);
      setAddWsId("");
      setAddWsRole("viewer");
    },
  });

  if (isLoading) return <div className="animate-pulse h-64 bg-zinc-800/30 rounded-lg" />;
  if (!user) return <div className="text-zinc-500">User not found</div>;

  const availableWorkspaces = allWorkspaces.filter(
    (ws) => !user.memberships.some((m) => m.workspace_id === ws.id)
  );

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
            {editingName ? (
              <div className="flex items-center gap-2">
                <input
                  value={nameValue}
                  onChange={(e) => setNameValue(e.target.value)}
                  className="px-2 py-1 bg-zinc-800 border border-zinc-700 rounded text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") updateName.mutate();
                    if (e.key === "Escape") setEditingName(false);
                  }}
                />
                <button
                  onClick={() => updateName.mutate()}
                  disabled={updateName.isPending || !nameValue}
                  className="text-xs text-emerald-400 hover:text-emerald-300"
                >
                  Save
                </button>
                <button onClick={() => setEditingName(false)} className="text-xs text-zinc-500 hover:text-zinc-300">
                  Cancel
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold">{user.name}</h2>
                <button
                  onClick={() => { setNameValue(user.name); setEditingName(true); }}
                  className="text-zinc-600 hover:text-zinc-400"
                  title="Edit name"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
              </div>
            )}
            <div className="text-sm text-zinc-400 mt-0.5">{user.email}</div>
            <div className="flex items-center gap-3 mt-2">
              <StatusBadge active={user.is_active} />
              {user.is_admin && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-purple-500/10 text-purple-400 ring-1 ring-purple-500/20">
                  Admin
                </span>
              )}
              <span className="text-xs text-zinc-500">
                Joined {new Date(user.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => setShowConfirmAdmin(true)}
              className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
                user.is_admin
                  ? "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
                  : "bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 ring-1 ring-purple-500/20"
              }`}
            >
              {user.is_admin ? "Demote Admin" : "Promote Admin"}
            </button>
            <button
              onClick={() => setShowConfirmRevoke(true)}
              className="px-3 py-1.5 rounded text-xs font-medium bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 ring-1 ring-amber-500/20 transition-colors"
            >
              Revoke Tokens
            </button>
            <button
              onClick={() => setShowConfirmToggle(true)}
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
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-sm font-medium text-zinc-400">
            Workspaces ({user.memberships.length})
          </h3>
          <button
            onClick={() => setShowAddWorkspace(true)}
            className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 transition-colors"
          >
            + Add to Workspace
          </button>
        </div>
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

      {/* Confirm deactivate/activate */}
      <ConfirmModal
        open={showConfirmToggle}
        onClose={() => setShowConfirmToggle(false)}
        onConfirm={() => toggleActive.mutate()}
        title={user.is_active ? "Deactivate User" : "Activate User"}
        message={
          user.is_active
            ? `Are you sure you want to deactivate ${user.name}? They will no longer be able to log in.`
            : `Are you sure you want to reactivate ${user.name}?`
        }
        confirmLabel={user.is_active ? "Deactivate" : "Activate"}
        danger={user.is_active}
        isPending={toggleActive.isPending}
      />

      {/* Confirm promote/demote admin */}
      <ConfirmModal
        open={showConfirmAdmin}
        onClose={() => setShowConfirmAdmin(false)}
        onConfirm={() => toggleAdmin.mutate()}
        title={user.is_admin ? "Demote Admin" : "Promote to Admin"}
        message={
          user.is_admin
            ? `Remove admin privileges from ${user.name}?`
            : `Grant admin privileges to ${user.name}? They will have full access to the admin panel.`
        }
        confirmLabel={user.is_admin ? "Demote" : "Promote"}
        danger={user.is_admin}
        isPending={toggleAdmin.isPending}
      />

      {/* Confirm revoke tokens */}
      <ConfirmModal
        open={showConfirmRevoke}
        onClose={() => setShowConfirmRevoke(false)}
        onConfirm={() => revokeTokens.mutate()}
        title="Revoke All Tokens"
        message={`This will invalidate all active sessions for ${user.name}. They will need to log in again.`}
        confirmLabel="Revoke All"
        danger
        isPending={revokeTokens.isPending}
      />

      {/* Add to workspace modal */}
      <Modal open={showAddWorkspace} onClose={() => setShowAddWorkspace(false)} title="Add to Workspace">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Workspace</label>
            <select
              value={addWsId}
              onChange={(e) => setAddWsId(e.target.value)}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-300"
            >
              <option value="">Select workspace...</option>
              {availableWorkspaces.map((ws) => (
                <option key={ws.id} value={ws.id}>
                  {ws.name} ({ws.slug})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-xs text-zinc-500">Role</label>
            <select
              value={addWsRole}
              onChange={(e) => setAddWsRole(e.target.value)}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-300"
            >
              {["viewer", "editor", "admin", "owner"].map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>
          {addToWorkspace.isError && (
            <div className="text-xs text-red-400">{(addToWorkspace.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowAddWorkspace(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => addToWorkspace.mutate()}
              disabled={!addWsId || addToWorkspace.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
