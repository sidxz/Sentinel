import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getWorkspace,
  getWorkspaceGroups,
  getWorkspaceMembers,
  inviteMember,
  removeMember,
  updateMemberRole,
} from "../api/client";
import { RoleBadge } from "../components/Badge";
import { Modal } from "../components/Modal";

const TABS = ["Members", "Groups"] as const;
type Tab = (typeof TABS)[number];

export function WorkspaceDetail() {
  const { id } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>("Members");
  const queryClient = useQueryClient();

  const { data: workspace } = useQuery({
    queryKey: ["workspace", id],
    queryFn: () => getWorkspace(id!),
    enabled: !!id,
  });

  if (!workspace) return <div className="animate-pulse h-64 bg-zinc-800/30 rounded-lg" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <Link to="/workspaces" className="hover:text-zinc-300">Workspaces</Link>
        <span>/</span>
        <span className="text-zinc-200">{workspace.name}</span>
      </div>

      {/* Header */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <h2 className="text-lg font-semibold">{workspace.name}</h2>
        <div className="text-sm text-zinc-400 mt-0.5">{workspace.slug}</div>
        {workspace.description && (
          <div className="text-sm text-zinc-500 mt-2">{workspace.description}</div>
        )}
        <div className="text-xs text-zinc-500 mt-2">
          Created {new Date(workspace.created_at).toLocaleDateString()}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-zinc-800">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
              tab === t
                ? "border-zinc-300 text-zinc-100"
                : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Members" && <MembersTab workspaceId={id!} />}
      {tab === "Groups" && <GroupsTab workspaceId={id!} />}
    </div>
  );
}

function MembersTab({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("viewer");

  const { data: members = [], isLoading } = useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => getWorkspaceMembers(workspaceId),
  });

  const invite = useMutation({
    mutationFn: () => inviteMember(workspaceId, inviteEmail, inviteRole),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] });
      setShowInvite(false);
      setInviteEmail("");
    },
  });

  const changeRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      updateMemberRole(workspaceId, userId, role),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] }),
  });

  const remove = useMutation({
    mutationFn: (userId: string) => removeMember(workspaceId, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] }),
  });

  if (isLoading) return <div className="h-32 bg-zinc-800/30 rounded-lg animate-pulse" />;

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button
          onClick={() => setShowInvite(true)}
          className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 transition-colors"
        >
          + Invite Member
        </button>
      </div>

      <div className="rounded-lg border border-zinc-800 divide-y divide-zinc-800/50">
        {members.map((m) => (
          <div key={m.user_id} className="flex items-center gap-3 px-4 py-3">
            <div className="w-7 h-7 rounded-full bg-zinc-700 flex items-center justify-center text-xs font-medium text-zinc-300 shrink-0">
              {m.name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <Link to={`/users/${m.user_id}`} className="text-sm font-medium hover:underline">{m.name}</Link>
              <div className="text-xs text-zinc-500">{m.email}</div>
            </div>
            <select
              value={m.role}
              onChange={(e) => changeRole.mutate({ userId: m.user_id, role: e.target.value })}
              className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-xs text-zinc-300"
            >
              {["owner", "admin", "editor", "viewer"].map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <button
              onClick={() => remove.mutate(m.user_id)}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Remove
            </button>
          </div>
        ))}
        {members.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No members</div>
        )}
      </div>

      <Modal open={showInvite} onClose={() => setShowInvite(false)} title="Invite Member">
        <div className="space-y-3">
          <input
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="user@example.com"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-300"
          >
            {["viewer", "editor", "admin", "owner"].map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowInvite(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => invite.mutate()}
              disabled={!inviteEmail || invite.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Invite
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function GroupsTab({ workspaceId }: { workspaceId: string }) {
  const { data: groups = [], isLoading } = useQuery({
    queryKey: ["workspace-groups", workspaceId],
    queryFn: () => getWorkspaceGroups(workspaceId),
  });

  if (isLoading) return <div className="h-32 bg-zinc-800/30 rounded-lg animate-pulse" />;

  return (
    <div className="rounded-lg border border-zinc-800 divide-y divide-zinc-800/50">
      {groups.map((g) => (
        <div key={g.id} className="px-4 py-3">
          <div className="text-sm font-medium">{g.name}</div>
          {g.description && <div className="text-xs text-zinc-500 mt-0.5">{g.description}</div>}
          <div className="text-xs text-zinc-600 mt-1">
            Created {new Date(g.created_at).toLocaleDateString()}
          </div>
        </div>
      ))}
      {groups.length === 0 && (
        <div className="px-4 py-8 text-center text-sm text-zinc-500">No groups</div>
      )}
    </div>
  );
}
