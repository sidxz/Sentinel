import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getWorkspaces } from "../api/client";
import { DataTable } from "../components/DataTable";
import { SearchInput } from "../components/SearchInput";
import type { Workspace } from "../types/api";

export function Workspaces() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["workspaces", page, search],
    queryFn: () => getWorkspaces(page, 20, search || undefined),
  });

  const columns = [
    {
      key: "name",
      header: "Workspace",
      render: (w: Workspace) => (
        <div>
          <div className="font-medium text-sm">{w.name}</div>
          <div className="text-xs text-zinc-500">{w.slug}</div>
        </div>
      ),
    },
    {
      key: "members",
      header: "Members",
      render: (w: Workspace) => <span className="text-zinc-400 tabular-nums">{w.member_count}</span>,
      className: "w-28",
    },
    {
      key: "description",
      header: "Description",
      render: (w: Workspace) => (
        <span className="text-zinc-500 text-sm truncate block max-w-xs">
          {w.description || "--"}
        </span>
      ),
    },
    {
      key: "created",
      header: "Created",
      render: (w: Workspace) => (
        <span className="text-zinc-500 text-xs">{new Date(w.created_at).toLocaleDateString()}</span>
      ),
      className: "w-28",
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Workspaces</h1>
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search workspaces..." />
      </div>

      {isLoading ? (
        <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />
      ) : (
        <>
          <DataTable
            columns={columns}
            data={data?.items ?? []}
            onRowClick={(w) => navigate(`/workspaces/${w.id}`)}
            emptyMessage="No workspaces found"
          />
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
