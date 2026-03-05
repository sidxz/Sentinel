import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getWorkspaces, createWorkspace, exportWorkspaces } from "../api/client";
import { DataTable } from "../components/DataTable";
import { Modal } from "../components/Modal";
import { SearchInput } from "../components/SearchInput";
import type { Workspace } from "../types/api";

export function Workspaces() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", description: "" });

  const { data, isLoading } = useQuery({
    queryKey: ["workspaces", page, search],
    queryFn: () => getWorkspaces(page, 20, search || undefined),
  });

  const create = useMutation({
    mutationFn: () =>
      createWorkspace({
        name: form.name,
        slug: form.slug,
        description: form.description || undefined,
      }),
    onSuccess: (ws) => {
      queryClient.invalidateQueries({ queryKey: ["workspaces"] });
      setShowCreate(false);
      setForm({ name: "", slug: "", description: "" });
      navigate(`/workspaces/${ws.id}`);
    },
  });

  const autoSlug = (name: string) =>
    name
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");

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
        <div className="flex items-center gap-3">
          <SearchInput value={search} onChange={(v) => { setSearch(v); setPage(1); }} placeholder="Search workspaces..." />
          <button
            onClick={() => exportWorkspaces()}
            className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 transition-colors"
          >
            Export CSV
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white transition-colors"
          >
            + Create Workspace
          </button>
        </div>
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

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create Workspace">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Name</label>
            <input
              value={form.name}
              onChange={(e) => {
                const name = e.target.value;
                setForm((f) => ({
                  ...f,
                  name,
                  slug: f.slug === autoSlug(f.name) ? autoSlug(name) : f.slug,
                }));
              }}
              placeholder="My Workspace"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">Slug</label>
            <input
              value={form.slug}
              onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
              placeholder="my-workspace"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">Description (optional)</label>
            <input
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          {create.isError && (
            <div className="text-xs text-red-400">{(create.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || !form.slug || create.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              {create.isPending ? "Creating..." : "Create"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
