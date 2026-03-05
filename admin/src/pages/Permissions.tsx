import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  adminGetPermission,
  adminListPermissions,
  adminRevokeShare,
  adminSharePermission,
  adminUpdateVisibility,
  getAllWorkspaces,
} from "../api/client";
import { VisibilityBadge } from "../components/Badge";
import { Modal } from "../components/Modal";
import { SearchInput } from "../components/SearchInput";
import type { AdminResourcePermission } from "../types/api";

export function Permissions() {
  const [page, setPage] = useState(1);
  const [workspaceFilter, setWorkspaceFilter] = useState("");
  const [serviceFilter, setServiceFilter] = useState("");
  const [resourceIdFilter, setResourceIdFilter] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("");
  const [sortBy, setSortBy] = useState<string | undefined>();
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: workspaces = [] } = useQuery({
    queryKey: ["all-workspaces"],
    queryFn: getAllWorkspaces,
  });

  const { data, isLoading } = useQuery({
    queryKey: ["admin-permissions", page, workspaceFilter, serviceFilter, resourceIdFilter, ownerFilter, sortBy, sortOrder],
    queryFn: () =>
      adminListPermissions({
        page,
        workspaceId: workspaceFilter || undefined,
        serviceName: serviceFilter || undefined,
        resourceId: resourceIdFilter || undefined,
        owner: ownerFilter || undefined,
        sortBy,
        sortOrder,
      }),
  });

  const toggleSort = (col: string) => {
    if (sortBy === col) {
      setSortOrder((o) => (o === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortOrder("desc");
    }
    setPage(1);
  };

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold">Permissions</h1>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={workspaceFilter}
          onChange={(e) => { setWorkspaceFilter(e.target.value); setPage(1); }}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-300"
        >
          <option value="">All workspaces</option>
          {workspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name} ({ws.slug})
            </option>
          ))}
        </select>
        <SearchInput value={serviceFilter} onChange={(v) => { setServiceFilter(v); setPage(1); }} placeholder="Service name..." />
        <SearchInput value={resourceIdFilter} onChange={(v) => { setResourceIdFilter(v); setPage(1); }} placeholder="Resource ID..." />
        <SearchInput value={ownerFilter} onChange={(v) => { setOwnerFilter(v); setPage(1); }} placeholder="Owner email..." />
      </div>

      {isLoading ? (
        <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />
      ) : (
        <>
          {/* Table */}
          <div className="rounded-lg border border-zinc-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-zinc-800/50 text-zinc-500 text-xs">
                <tr>
                  <th className="text-left px-4 py-2 font-medium">Service</th>
                  <th className="text-left px-4 py-2 font-medium">Type</th>
                  <th className="text-left px-4 py-2 font-medium">Resource ID</th>
                  <th className="text-left px-4 py-2 font-medium">Owner</th>
                  <th className="text-left px-4 py-2 font-medium">Visibility</th>
                  <th
                    className="text-left px-4 py-2 font-medium w-20 cursor-pointer select-none hover:text-zinc-300 transition-colors"
                    onClick={() => toggleSort("shares")}
                  >
                    Shares{sortBy === "shares" ? (sortOrder === "asc" ? " \u2191" : " \u2193") : ""}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {(data?.items ?? []).map((p) => (
                  <PermissionRow
                    key={p.id}
                    perm={p}
                    expanded={expandedId === p.id}
                    onToggle={() => setExpandedId(expandedId === p.id ? null : p.id)}
                  />
                ))}
              </tbody>
            </table>
            {(data?.items ?? []).length === 0 && (
              <div className="px-4 py-12 text-center text-sm text-zinc-500">No resources found</div>
            )}
          </div>

          {/* Pagination */}
          {data && data.total > data.page_size && (
            <div className="flex items-center justify-between text-xs text-zinc-500">
              <span>{data.total} total</span>
              <div className="flex gap-1">
                <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30">Prev</button>
                <span className="px-2 py-1">{data.page} / {Math.ceil(data.total / data.page_size)}</span>
                <button disabled={page >= Math.ceil(data.total / data.page_size)} onClick={() => setPage(page + 1)} className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30">Next</button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function PermissionRow({
  perm,
  expanded,
  onToggle,
}: {
  perm: AdminResourcePermission;
  expanded: boolean;
  onToggle: () => void;
}) {
  const queryClient = useQueryClient();
  const [showShare, setShowShare] = useState(false);
  const [shareForm, setShareForm] = useState({ grantee_type: "user", grantee_id: "", permission: "view" });

  const { data: detail } = useQuery({
    queryKey: ["admin-permission", perm.id],
    queryFn: () => adminGetPermission(perm.id),
    enabled: expanded,
  });

  const toggleVisibility = useMutation({
    mutationFn: () =>
      adminUpdateVisibility(perm.id, perm.visibility === "workspace" ? "private" : "workspace"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-permissions"] });
      queryClient.invalidateQueries({ queryKey: ["admin-permission", perm.id] });
    },
  });

  const revoke = useMutation({
    mutationFn: ({ granteeType, granteeId }: { granteeType: string; granteeId: string }) =>
      adminRevokeShare(perm.id, granteeType, granteeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-permission", perm.id] });
      queryClient.invalidateQueries({ queryKey: ["admin-permissions"] });
    },
  });

  const share = useMutation({
    mutationFn: () =>
      adminSharePermission(perm.id, shareForm),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-permission", perm.id] });
      queryClient.invalidateQueries({ queryKey: ["admin-permissions"] });
      setShowShare(false);
      setShareForm({ grantee_type: "user", grantee_id: "", permission: "view" });
    },
  });

  return (
    <>
      <tr
        onClick={onToggle}
        className="hover:bg-zinc-800/40 cursor-pointer transition-colors"
      >
        <td className="px-4 py-2.5 font-mono text-zinc-300">{perm.service_name}</td>
        <td className="px-4 py-2.5 font-mono text-zinc-400">{perm.resource_type}</td>
        <td className="px-4 py-2.5 font-mono text-xs text-zinc-500">{String(perm.resource_id).slice(0, 8)}...</td>
        <td className="px-4 py-2.5 text-zinc-400 text-xs">{perm.owner_email ?? "—"}</td>
        <td className="px-4 py-2.5"><VisibilityBadge visibility={perm.visibility} /></td>
        <td className="px-4 py-2.5 text-zinc-400 tabular-nums">{perm.share_count}</td>
      </tr>

      {expanded && detail && (
        <tr>
          <td colSpan={6} className="px-4 py-4 bg-zinc-800/20 border-t border-zinc-800/50">
            <div className="space-y-4">
              {/* Details */}
              <dl className="grid grid-cols-3 gap-x-6 gap-y-2 text-xs">
                <div>
                  <dt className="text-zinc-500">Resource ID</dt>
                  <dd className="font-mono text-zinc-300">{String(detail.resource_id)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Owner</dt>
                  <dd className="text-zinc-300">{detail.owner_email ?? String(detail.owner_id)}</dd>
                </div>
                <div>
                  <dt className="text-zinc-500">Created</dt>
                  <dd className="text-zinc-300">{new Date(detail.created_at).toLocaleString()}</dd>
                </div>
              </dl>

              {/* Visibility toggle */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-zinc-500">Visibility:</span>
                <button
                  onClick={(e) => { e.stopPropagation(); toggleVisibility.mutate(); }}
                  disabled={toggleVisibility.isPending}
                  className="text-xs px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                >
                  Switch to {detail.visibility === "workspace" ? "private" : "workspace"}
                </button>
              </div>

              {/* Shares */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-zinc-500 font-medium">Shares ({detail.shares.length})</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); setShowShare(true); }}
                    className="text-xs px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                  >
                    + Add Share
                  </button>
                </div>
                {detail.shares.length > 0 ? (
                  <div className="rounded border border-zinc-800 divide-y divide-zinc-800/50">
                    {detail.shares.map((s) => (
                      <div key={s.id} className="flex items-center justify-between px-3 py-2 text-xs">
                        <div>
                          <span className="capitalize text-zinc-400">{s.grantee_type}</span>{" "}
                          <span className="font-mono text-zinc-500">{s.grantee_id}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className={`font-medium ${s.permission === "edit" ? "text-blue-400" : "text-zinc-400"}`}>
                            {s.permission}
                          </span>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              revoke.mutate({ granteeType: s.grantee_type, granteeId: s.grantee_id });
                            }}
                            className="text-red-400 hover:text-red-300"
                          >
                            Revoke
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xs text-zinc-600">No shares</div>
                )}
              </div>
            </div>

            {/* Add share modal */}
            <Modal open={showShare} onClose={() => setShowShare(false)} title="Add Share">
              <div className="space-y-3">
                <div>
                  <label className="text-xs text-zinc-500">Grantee Type</label>
                  <select
                    value={shareForm.grantee_type}
                    onChange={(e) => setShareForm((f) => ({ ...f, grantee_type: e.target.value }))}
                    className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-300"
                  >
                    <option value="user">User</option>
                    <option value="group">Group</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-zinc-500">Grantee ID (UUID)</label>
                  <input
                    value={shareForm.grantee_id}
                    onChange={(e) => setShareForm((f) => ({ ...f, grantee_id: e.target.value }))}
                    placeholder="UUID"
                    className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
                  />
                </div>
                <div>
                  <label className="text-xs text-zinc-500">Permission</label>
                  <select
                    value={shareForm.permission}
                    onChange={(e) => setShareForm((f) => ({ ...f, permission: e.target.value }))}
                    className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-300"
                  >
                    <option value="view">View</option>
                    <option value="edit">Edit</option>
                  </select>
                </div>
                {share.isError && (
                  <div className="text-xs text-red-400">{(share.error as Error).message}</div>
                )}
                <div className="flex justify-end gap-2 pt-2">
                  <button onClick={() => setShowShare(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
                  <button
                    onClick={() => share.mutate()}
                    disabled={!shareForm.grantee_id || share.isPending}
                    className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
                  >
                    Share
                  </button>
                </div>
              </div>
            </Modal>
          </td>
        </tr>
      )}
    </>
  );
}
