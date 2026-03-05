import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  addGroupMember,
  addRoleActions,
  addRoleMember,
  createGroup,
  createRole,
  deleteGroup,
  deleteRole,
  deleteWorkspace,
  getGroupMembers,
  getRoleActions,
  getRoleMembers,
  getServiceActions,
  getWorkspace,
  getWorkspaceGroups,
  getWorkspaceMembers,
  getWorkspaceRoles,
  inviteMember,
  removeMember,
  removeGroupMember,
  removeRoleAction,
  removeRoleMember,
  updateGroup,
  updateMemberRole,
  updateRole,
  updateWorkspace,
} from "../api/client";
import { RoleBadge } from "../components/Badge";
import { ConfirmModal } from "../components/ConfirmModal";
import { Modal } from "../components/Modal";

const TABS = ["Members", "Groups", "Roles"] as const;
type Tab = (typeof TABS)[number];

export function WorkspaceDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<Tab>("Members");
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [deleteSlug, setDeleteSlug] = useState("");
  const [editForm, setEditForm] = useState({ name: "", description: "" });

  const { data: workspace } = useQuery({
    queryKey: ["workspace", id],
    queryFn: () => getWorkspace(id!),
    enabled: !!id,
  });

  const update = useMutation({
    mutationFn: () =>
      updateWorkspace(id!, {
        name: editForm.name || undefined,
        description: editForm.description,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace", id] });
      setShowEdit(false);
    },
  });

  const remove = useMutation({
    mutationFn: () => deleteWorkspace(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      navigate("/workspaces");
    },
  });

  const openEdit = () => {
    if (workspace) {
      setEditForm({ name: workspace.name, description: workspace.description ?? "" });
    }
    setShowEdit(true);
  };

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
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold">{workspace.name}</h2>
            <div className="text-sm text-zinc-400 mt-0.5">{workspace.slug}</div>
            {workspace.description && (
              <div className="text-sm text-zinc-500 mt-2">{workspace.description}</div>
            )}
            <div className="text-xs text-zinc-500 mt-2">
              Created {new Date(workspace.created_at).toLocaleDateString()}
              {" · "}{workspace.member_count} members · {workspace.group_count} groups
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={openEdit}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 transition-colors"
            >
              Edit
            </button>
            <button
              onClick={() => { setShowDelete(true); setDeleteSlug(""); }}
              className="px-3 py-1.5 rounded text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 ring-1 ring-red-500/20 transition-colors"
            >
              Delete
            </button>
          </div>
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
      {tab === "Roles" && <RolesTab workspaceId={id!} />}

      {/* Edit modal */}
      <Modal open={showEdit} onClose={() => setShowEdit(false)} title="Edit Workspace">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Name</label>
            <input
              value={editForm.name}
              onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">Description</label>
            <input
              value={editForm.description}
              onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowEdit(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => update.mutate()}
              disabled={update.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <ConfirmModal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={() => remove.mutate()}
        title="Delete Workspace"
        message={`This will permanently delete "${workspace.name}" and all its memberships and groups.`}
        confirmLabel="Delete Workspace"
        danger
        isPending={remove.isPending}
        confirmInput={workspace.slug}
        confirmInputValue={deleteSlug}
        onConfirmInputChange={setDeleteSlug}
      />
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
          {invite.isError && (
            <div className="text-xs text-red-400">{(invite.error as Error).message}</div>
          )}
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
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editingGroup, setEditingGroup] = useState<string | null>(null);
  const [expandedGroup, setExpandedGroup] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", description: "" });
  const [addMemberEmail, setAddMemberEmail] = useState("");

  const { data: groups = [], isLoading } = useQuery({
    queryKey: ["workspace-groups", workspaceId],
    queryFn: () => getWorkspaceGroups(workspaceId),
  });

  const { data: members = [] } = useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => getWorkspaceMembers(workspaceId),
  });

  const { data: groupMembers = [] } = useQuery({
    queryKey: ["group-members", expandedGroup],
    queryFn: () => getGroupMembers(expandedGroup!),
    enabled: !!expandedGroup,
  });

  const create = useMutation({
    mutationFn: () => createGroup(workspaceId, { name: form.name, description: form.description || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-groups", workspaceId] });
      setShowCreate(false);
      setForm({ name: "", description: "" });
    },
  });

  const edit = useMutation({
    mutationFn: () => updateGroup(editingGroup!, { name: form.name, description: form.description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-groups", workspaceId] });
      setEditingGroup(null);
      setForm({ name: "", description: "" });
    },
  });

  const del = useMutation({
    mutationFn: (gid: string) => deleteGroup(gid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-groups", workspaceId] });
      setExpandedGroup(null);
    },
  });

  const addMember = useMutation({
    mutationFn: (userId: string) => addGroupMember(expandedGroup!, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["group-members", expandedGroup] });
      setAddMemberEmail("");
    },
  });

  const removeMemberMut = useMutation({
    mutationFn: (userId: string) => removeGroupMember(expandedGroup!, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["group-members", expandedGroup] }),
  });

  if (isLoading) return <div className="h-32 bg-zinc-800/30 rounded-lg animate-pulse" />;

  const selectedMember = members.find((m) => m.email === addMemberEmail);

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button
          onClick={() => { setShowCreate(true); setForm({ name: "", description: "" }); }}
          className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 transition-colors"
        >
          + Create Group
        </button>
      </div>

      <div className="rounded-lg border border-zinc-800 divide-y divide-zinc-800/50">
        {groups.map((g) => (
          <div key={g.id}>
            <div
              className="flex items-center justify-between px-4 py-3 hover:bg-zinc-800/40 cursor-pointer transition-colors"
              onClick={() => setExpandedGroup(expandedGroup === g.id ? null : g.id)}
            >
              <div>
                <div className="text-sm font-medium">{g.name}</div>
                {g.description && <div className="text-xs text-zinc-500 mt-0.5">{g.description}</div>}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingGroup(g.id);
                    setForm({ name: g.name, description: g.description ?? "" });
                  }}
                  className="text-xs text-zinc-500 hover:text-zinc-300"
                >
                  Edit
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); del.mutate(g.id); }}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  Delete
                </button>
                <span className="text-xs text-zinc-600">{expandedGroup === g.id ? "▲" : "▼"}</span>
              </div>
            </div>

            {/* Expanded group members */}
            {expandedGroup === g.id && (
              <div className="px-4 pb-3 space-y-2 bg-zinc-800/20">
                <div className="flex items-center gap-2 pt-2">
                  <select
                    value={addMemberEmail}
                    onChange={(e) => setAddMemberEmail(e.target.value)}
                    className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-300"
                  >
                    <option value="">Select member to add...</option>
                    {members
                      .filter((m) => !groupMembers.some((gm) => gm.user_id === m.user_id))
                      .map((m) => (
                        <option key={m.user_id} value={m.email}>
                          {m.name} ({m.email})
                        </option>
                      ))}
                  </select>
                  <button
                    onClick={() => {
                      if (selectedMember) addMember.mutate(selectedMember.user_id);
                    }}
                    disabled={!selectedMember || addMember.isPending}
                    className="px-2 py-1.5 rounded text-xs font-medium bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50"
                  >
                    Add
                  </button>
                </div>
                <div className="divide-y divide-zinc-800/50">
                  {groupMembers.map((gm) => (
                    <div key={gm.user_id} className="flex items-center justify-between py-2">
                      <div className="text-sm">
                        <span className="text-zinc-300">{gm.name}</span>
                        <span className="text-zinc-500 ml-2 text-xs">{gm.email}</span>
                      </div>
                      <button
                        onClick={() => removeMemberMut.mutate(gm.user_id)}
                        className="text-xs text-red-400 hover:text-red-300"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                  {groupMembers.length === 0 && (
                    <div className="py-2 text-xs text-zinc-500">No members in this group</div>
                  )}
                </div>
              </div>
            )}
          </div>
        ))}
        {groups.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No groups</div>
        )}
      </div>

      {/* Create group modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create Group">
        <div className="space-y-3">
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Group name"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <input
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Description (optional)"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          {create.isError && (
            <div className="text-xs text-red-400">{(create.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || create.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Create
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit group modal */}
      <Modal open={!!editingGroup} onClose={() => setEditingGroup(null)} title="Edit Group">
        <div className="space-y-3">
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <input
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Description"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setEditingGroup(null)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => edit.mutate()}
              disabled={edit.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

function RolesTab({ workspaceId }: { workspaceId: string }) {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editingRole, setEditingRole] = useState<string | null>(null);
  const [expandedRole, setExpandedRole] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", description: "" });
  const [selectedActionId, setSelectedActionId] = useState("");
  const [addMemberEmail, setAddMemberEmail] = useState("");

  const { data: roles = [], isLoading } = useQuery({
    queryKey: ["workspace-roles", workspaceId],
    queryFn: () => getWorkspaceRoles(workspaceId),
  });

  const { data: members = [] } = useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => getWorkspaceMembers(workspaceId),
  });

  const { data: allActions = [] } = useQuery({
    queryKey: ["service-actions"],
    queryFn: () => getServiceActions(),
  });

  const { data: roleActions = [] } = useQuery({
    queryKey: ["role-actions", expandedRole],
    queryFn: () => getRoleActions(expandedRole!),
    enabled: !!expandedRole,
  });

  const { data: roleMembers = [] } = useQuery({
    queryKey: ["role-members", expandedRole],
    queryFn: () => getRoleMembers(expandedRole!),
    enabled: !!expandedRole,
  });

  const create = useMutation({
    mutationFn: () => createRole(workspaceId, { name: form.name, description: form.description || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-roles", workspaceId] });
      setShowCreate(false);
      setForm({ name: "", description: "" });
    },
  });

  const edit = useMutation({
    mutationFn: () => updateRole(editingRole!, { name: form.name, description: form.description }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-roles", workspaceId] });
      setEditingRole(null);
      setForm({ name: "", description: "" });
    },
  });

  const del = useMutation({
    mutationFn: (rid: string) => deleteRole(rid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workspace-roles", workspaceId] });
      setExpandedRole(null);
    },
  });

  const addAction = useMutation({
    mutationFn: (actionId: string) => addRoleActions(expandedRole!, [actionId]),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["role-actions", expandedRole] });
      queryClient.invalidateQueries({ queryKey: ["workspace-roles", workspaceId] });
      setSelectedActionId("");
    },
  });

  const removeAction = useMutation({
    mutationFn: (actionId: string) => removeRoleAction(expandedRole!, actionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["role-actions", expandedRole] });
      queryClient.invalidateQueries({ queryKey: ["workspace-roles", workspaceId] });
    },
  });

  const addMember = useMutation({
    mutationFn: (userId: string) => addRoleMember(expandedRole!, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["role-members", expandedRole] });
      queryClient.invalidateQueries({ queryKey: ["workspace-roles", workspaceId] });
      setAddMemberEmail("");
    },
  });

  const removeMemberMut = useMutation({
    mutationFn: (userId: string) => removeRoleMember(expandedRole!, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["role-members", expandedRole] });
      queryClient.invalidateQueries({ queryKey: ["workspace-roles", workspaceId] });
    },
  });

  if (isLoading) return <div className="h-32 bg-zinc-800/30 rounded-lg animate-pulse" />;

  const availableActions = allActions.filter(
    (a) => !roleActions.some((ra) => ra.id === a.id),
  );
  const selectedMember = members.find((m) => m.email === addMemberEmail);

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <button
          onClick={() => { setShowCreate(true); setForm({ name: "", description: "" }); }}
          className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 transition-colors"
        >
          + Create Role
        </button>
      </div>

      <div className="rounded-lg border border-zinc-800 divide-y divide-zinc-800/50">
        {roles.map((r) => (
          <div key={r.id}>
            <div
              className="flex items-center justify-between px-4 py-3 hover:bg-zinc-800/40 cursor-pointer transition-colors"
              onClick={() => setExpandedRole(expandedRole === r.id ? null : r.id)}
            >
              <div>
                <div className="text-sm font-medium">{r.name}</div>
                {r.description && <div className="text-xs text-zinc-500 mt-0.5">{r.description}</div>}
                <div className="text-xs text-zinc-600 mt-0.5">
                  {r.action_count} actions · {r.member_count} members
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setEditingRole(r.id);
                    setForm({ name: r.name, description: r.description ?? "" });
                  }}
                  className="text-xs text-zinc-500 hover:text-zinc-300"
                >
                  Edit
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); del.mutate(r.id); }}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  Delete
                </button>
                <span className="text-xs text-zinc-600">{expandedRole === r.id ? "▲" : "▼"}</span>
              </div>
            </div>

            {/* Expanded role detail */}
            {expandedRole === r.id && (
              <div className="px-4 pb-3 space-y-4 bg-zinc-800/20">
                {/* Actions section */}
                <div>
                  <div className="text-xs font-medium text-zinc-400 pt-2 pb-1">Actions</div>
                  <div className="flex items-center gap-2">
                    <select
                      value={selectedActionId}
                      onChange={(e) => setSelectedActionId(e.target.value)}
                      className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-300"
                    >
                      <option value="">Select action to add...</option>
                      {availableActions.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.service_name}:{a.action}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => { if (selectedActionId) addAction.mutate(selectedActionId); }}
                      disabled={!selectedActionId || addAction.isPending}
                      className="px-2 py-1.5 rounded text-xs font-medium bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50"
                    >
                      Add
                    </button>
                  </div>
                  <div className="divide-y divide-zinc-800/50 mt-1">
                    {roleActions.map((a) => (
                      <div key={a.id} className="flex items-center justify-between py-2">
                        <div className="text-sm">
                          <span className="text-zinc-300">{a.service_name}:{a.action}</span>
                          {a.description && <span className="text-zinc-500 ml-2 text-xs">{a.description}</span>}
                        </div>
                        <button
                          onClick={() => removeAction.mutate(a.id)}
                          className="text-xs text-red-400 hover:text-red-300"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    {roleActions.length === 0 && (
                      <div className="py-2 text-xs text-zinc-500">No actions assigned</div>
                    )}
                  </div>
                </div>

                {/* Members section */}
                <div>
                  <div className="text-xs font-medium text-zinc-400 pb-1">Members</div>
                  <div className="flex items-center gap-2">
                    <select
                      value={addMemberEmail}
                      onChange={(e) => setAddMemberEmail(e.target.value)}
                      className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-zinc-300"
                    >
                      <option value="">Select member to add...</option>
                      {members
                        .filter((m) => !roleMembers.some((rm) => rm.user_id === m.user_id))
                        .map((m) => (
                          <option key={m.user_id} value={m.email}>
                            {m.name} ({m.email})
                          </option>
                        ))}
                    </select>
                    <button
                      onClick={() => { if (selectedMember) addMember.mutate(selectedMember.user_id); }}
                      disabled={!selectedMember || addMember.isPending}
                      className="px-2 py-1.5 rounded text-xs font-medium bg-zinc-700 hover:bg-zinc-600 disabled:opacity-50"
                    >
                      Add
                    </button>
                  </div>
                  <div className="divide-y divide-zinc-800/50 mt-1">
                    {roleMembers.map((rm) => (
                      <div key={rm.user_id} className="flex items-center justify-between py-2">
                        <div className="text-sm">
                          <span className="text-zinc-300">{rm.name}</span>
                          <span className="text-zinc-500 ml-2 text-xs">{rm.email}</span>
                        </div>
                        <button
                          onClick={() => removeMemberMut.mutate(rm.user_id)}
                          className="text-xs text-red-400 hover:text-red-300"
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    {roleMembers.length === 0 && (
                      <div className="py-2 text-xs text-zinc-500">No members in this role</div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
        {roles.length === 0 && (
          <div className="px-4 py-8 text-center text-sm text-zinc-500">No roles</div>
        )}
      </div>

      {/* Create role modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create Role">
        <div className="space-y-3">
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Role name"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <input
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Description (optional)"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          {create.isError && (
            <div className="text-xs text-red-400">{(create.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || create.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Create
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit role modal */}
      <Modal open={!!editingRole} onClose={() => setEditingRole(null)} title="Edit Role">
        <div className="space-y-3">
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <input
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Description"
            className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setEditingRole(null)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => edit.mutate()}
              disabled={edit.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
