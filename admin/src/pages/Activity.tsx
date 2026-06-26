import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { getActivity, getAllWorkspaces } from "../api/client";
import type { ActivityLog } from "../types/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function Activity() {
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [targetType, setTargetType] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["activity", page, action, targetType, workspaceId, fromDate, toDate],
    queryFn: () =>
      getActivity({
        page,
        page_size: 25,
        action: action || undefined,
        target_type: targetType || undefined,
        workspace_id: workspaceId || undefined,
        from_date: fromDate || undefined,
        to_date: toDate || undefined,
      }),
  });

  const { data: workspaces = [] } = useQuery({
    queryKey: ["all-workspaces"],
    queryFn: getAllWorkspaces,
  });

  const actions = [
    "user_activated", "user_deactivated", "user_updated",
    "user_promoted_admin", "user_demoted_admin",
    "workspace_created", "workspace_updated", "workspace_deleted",
    "member_invited", "member_role_changed", "member_removed",
    "group_created", "group_updated", "group_deleted",
    "group_member_added", "group_member_removed",
    "permission_visibility_changed", "permission_shared", "permission_revoked",
    "batch_import", "bulk_status_change", "tokens_revoked",
    "org_create", "org_update", "org_public_toggle", "org_delete",
    "org_domain_add", "org_domain_remove", "workspace_allowed_orgs_set",
  ];

  const targetTypes = [
    "user", "workspace", "group", "resource_permission", "system", "organization",
  ];

  const resetFilters = () => {
    setAction("");
    setTargetType("");
    setWorkspaceId("");
    setFromDate("");
    setToDate("");
    setPage(1);
  };

  const totalPages = data ? Math.ceil(data.total / data.page_size) : 0;

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-semibold">Activity Log</h1>

      {/* Filters */}
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Action</label>
          <select
            value={action}
            onChange={(e) => { setAction(e.target.value); setPage(1); }}
            className="px-2 py-1.5 border border-border bg-background rounded text-xs text-foreground"
          >
            <option value="">All actions</option>
            {actions.map((a) => (
              <option key={a} value={a}>{a.replace(/_/g, " ")}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Target Type</label>
          <select
            value={targetType}
            onChange={(e) => { setTargetType(e.target.value); setPage(1); }}
            className="px-2 py-1.5 border border-border bg-background rounded text-xs text-foreground"
          >
            <option value="">All types</option>
            {targetTypes.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Workspace</label>
          <select
            value={workspaceId}
            onChange={(e) => { setWorkspaceId(e.target.value); setPage(1); }}
            className="px-2 py-1.5 border border-border bg-background rounded text-xs text-foreground"
          >
            <option value="">All workspaces</option>
            {workspaces.map((ws) => (
              <option key={ws.id} value={ws.id}>{ws.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1">From</label>
          <Input
            type="date"
            value={fromDate}
            onChange={(e) => { setFromDate(e.target.value); setPage(1); }}
            className="w-auto text-xs"
          />
        </div>
        <div>
          <label className="text-xs text-muted-foreground block mb-1">To</label>
          <Input
            type="date"
            value={toDate}
            onChange={(e) => { setToDate(e.target.value); setPage(1); }}
            className="w-auto text-xs"
          />
        </div>
        {(action || targetType || workspaceId || fromDate || toDate) && (
          <Button variant="ghost" size="sm" onClick={resetFilters}>
            Clear filters
          </Button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="h-64 bg-muted/50 rounded-lg animate-pulse" />
      ) : (
        <>
          <div className="rounded-lg border border-border divide-y divide-border">
            <div className="grid grid-cols-[1fr_120px_100px_100px_140px] px-4 py-2 text-xs text-muted-foreground font-medium">
              <span>Action</span>
              <span>Actor</span>
              <span>Target</span>
              <span>Workspace</span>
              <span>Time</span>
            </div>
            {data?.items.map((entry) => (
              <ActivityRow key={entry.id} entry={entry} />
            ))}
            {data?.items.length === 0 && (
              <div className="px-4 py-8 text-center text-sm text-muted-foreground">No activity found</div>
            )}
          </div>

          {data && data.total > data.page_size && (
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{data.total} total</span>
              <div className="flex items-center gap-1">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  Prev
                </Button>
                <span className="px-2 py-1">{page} / {totalPages}</span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ActivityRow({ entry }: { entry: ActivityLog }) {
  const action = entry.action.replace(/_/g, " ");
  const time = new Date(entry.created_at).toLocaleString();

  return (
    <div className="grid grid-cols-[1fr_120px_100px_100px_140px] px-4 py-2.5 text-sm items-center">
      <div className="flex items-center gap-2">
        <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/40 shrink-0" />
        <span className="text-foreground">{action}</span>
        {entry.detail &&
          Object.entries(entry.detail).map(([k, v]) => (
            <span key={k} className="text-muted-foreground text-xs">
              {k}: <span className="font-mono text-muted-foreground">{String(v)}</span>
            </span>
          ))}
      </div>
      <span className="text-muted-foreground text-xs truncate">{entry.actor_name ?? entry.actor_email ?? "System"}</span>
      <span className="text-muted-foreground text-xs">{entry.target_type}</span>
      <span className="font-mono text-muted-foreground text-xs truncate">{entry.workspace_id?.slice(0, 8) ?? "--"}</span>
      <span className="text-muted-foreground text-xs">{time}</span>
    </div>
  );
}
