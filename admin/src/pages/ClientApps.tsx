import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { createClientApp, getClientApps } from "../api/client";
import { DataTable } from "../components/DataTable";
import { Modal } from "../components/Modal";
import { StatusBadge } from "../components/Badge";
import type { ClientApp } from "../types/api";

export function ClientApps() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", redirect_uris: "" });

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ["client-apps"],
    queryFn: getClientApps,
  });

  const create = useMutation({
    mutationFn: () =>
      createClientApp({
        name: form.name,
        redirect_uris: form.redirect_uris
          .split("\n")
          .map((u) => u.trim())
          .filter(Boolean),
      }),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["client-apps"] });
      setShowCreate(false);
      setForm({ name: "", redirect_uris: "" });
      toast.success("App registered");
      navigate(`/client-apps/${result.id}`);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const columns = [
    {
      key: "name",
      header: "Name",
      render: (a: ClientApp) => <span className="font-medium text-sm">{a.name}</span>,
    },
    {
      key: "uris",
      header: "URIs",
      render: (a: ClientApp) => (
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ring-1 ring-inset bg-zinc-500/15 text-zinc-400 ring-zinc-500/20">
          {a.redirect_uris.length}
        </span>
      ),
      className: "w-20",
    },
    {
      key: "status",
      header: "Status",
      render: (a: ClientApp) => <StatusBadge active={a.is_active} />,
      className: "w-24",
    },
    {
      key: "created",
      header: "Created",
      render: (a: ClientApp) => (
        <span className="text-zinc-500 text-xs">{new Date(a.created_at).toLocaleDateString()}</span>
      ),
      className: "w-28",
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Client Apps</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white transition-colors"
        >
          + Register App
        </button>
      </div>

      {isLoading ? (
        <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />
      ) : (
        <DataTable
          columns={columns}
          data={apps}
          onRowClick={(a) => navigate(`/client-apps/${a.id}`)}
          emptyMessage="No client apps registered"
        />
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Register Client App">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="My Application"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">Redirect URIs (one per line)</label>
            <textarea
              value={form.redirect_uris}
              onChange={(e) => setForm((f) => ({ ...f, redirect_uris: e.target.value }))}
              placeholder={"https://app.example.com/callback\nhttp://localhost:3000/callback"}
              rows={3}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600 resize-none"
            />
          </div>
          {create.isError && (
            <div className="text-xs text-red-400">{(create.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || !form.redirect_uris.trim() || create.isPending}
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
