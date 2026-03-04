import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getUsers } from "../api/client";
import { StatusBadge } from "../components/Badge";
import { DataTable } from "../components/DataTable";
import { SearchInput } from "../components/SearchInput";
import type { User } from "../types/api";

export function Users() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["users", page, search],
    queryFn: () => getUsers(page, 20, search || undefined),
  });

  const columns = [
    {
      key: "name",
      header: "User",
      render: (u: User) => (
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-zinc-700 flex items-center justify-center text-xs font-medium text-zinc-300 shrink-0">
            {u.name.charAt(0).toUpperCase()}
          </div>
          <div>
            <div className="font-medium text-sm">{u.name}</div>
            <div className="text-xs text-zinc-500">{u.email}</div>
          </div>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (u: User) => <StatusBadge active={u.is_active} />,
      className: "w-28",
    },
    {
      key: "workspaces",
      header: "Workspaces",
      render: (u: User) => <span className="text-zinc-400 tabular-nums">{u.workspace_count}</span>,
      className: "w-28",
    },
    {
      key: "created",
      header: "Joined",
      render: (u: User) => (
        <span className="text-zinc-500 text-xs">{new Date(u.created_at).toLocaleDateString()}</span>
      ),
      className: "w-28",
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Users</h1>
        <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search users..." />
      </div>

      {isLoading ? (
        <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />
      ) : (
        <>
          <DataTable
            columns={columns}
            data={data?.items ?? []}
            onRowClick={(u) => navigate(`/users/${u.id}`)}
            emptyMessage="No users found"
          />
          {data && data.total > data.page_size && (
            <Pagination page={data.page} total={data.total} pageSize={data.page_size} onChange={setPage} />
          )}
        </>
      )}
    </div>
  );
}

function Pagination({ page, total, pageSize, onChange }: { page: number; total: number; pageSize: number; onChange: (p: number) => void }) {
  const totalPages = Math.ceil(total / pageSize);
  return (
    <div className="flex items-center justify-between text-xs text-zinc-500">
      <span>{total} total</span>
      <div className="flex gap-1">
        <button disabled={page <= 1} onClick={() => onChange(page - 1)} className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed">Prev</button>
        <span className="px-2 py-1">{page} / {totalPages}</span>
        <button disabled={page >= totalPages} onClick={() => onChange(page + 1)} className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-30 disabled:cursor-not-allowed">Next</button>
      </div>
    </div>
  );
}
