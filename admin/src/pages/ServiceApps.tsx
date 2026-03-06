import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { createServiceApp, getServiceApps } from "../api/client";
import { DataTable } from "../components/DataTable";
import { Modal } from "../components/Modal";
import { StatusBadge } from "../components/Badge";
import type { ServiceApp, ServiceAppCreateResponse } from "../types/api";

function KeyRevealModal({
  open,
  onClose,
  apiKey,
}: {
  open: boolean;
  onClose: () => void;
  apiKey: string;
}) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Modal open={open} onClose={onClose} title="API Key Created">
      <div className="space-y-4">
        <div className="text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded px-3 py-2">
          Copy this key now. It will not be shown again.
        </div>
        <div className="flex items-center gap-2">
          <code className="flex-1 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono break-all select-all">
            {apiKey}
          </code>
          <button
            onClick={copy}
            className="shrink-0 px-3 py-2 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white transition-colors"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <div className="flex justify-end pt-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    </Modal>
  );
}

export function ServiceApps() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", service_name: "" });
  const [revealKey, setRevealKey] = useState<string | null>(null);

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ["service-apps"],
    queryFn: getServiceApps,
  });

  const create = useMutation({
    mutationFn: () =>
      createServiceApp({ name: form.name, service_name: form.service_name }),
    onSuccess: (result: ServiceAppCreateResponse) => {
      queryClient.invalidateQueries({ queryKey: ["service-apps"] });
      setShowCreate(false);
      setForm({ name: "", service_name: "" });
      toast.success("Service registered");
      setRevealKey(result.api_key);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const columns = [
    {
      key: "name",
      header: "Name",
      render: (a: ServiceApp) => <span className="font-medium text-sm">{a.name}</span>,
    },
    {
      key: "service_name",
      header: "Service Name",
      render: (a: ServiceApp) => (
        <code className="text-xs text-zinc-400 font-mono">{a.service_name}</code>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (a: ServiceApp) => <StatusBadge active={a.is_active} />,
      className: "w-24",
    },
    {
      key: "last_used",
      header: "Last Used",
      render: (a: ServiceApp) => (
        <span className="text-zinc-500 text-xs">
          {a.last_used_at ? new Date(a.last_used_at).toLocaleDateString() : "Never"}
        </span>
      ),
      className: "w-28",
    },
    {
      key: "created",
      header: "Created",
      render: (a: ServiceApp) => (
        <span className="text-zinc-500 text-xs">{new Date(a.created_at).toLocaleDateString()}</span>
      ),
      className: "w-28",
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Service Apps</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white transition-colors"
        >
          + Register Service
        </button>
      </div>

      {isLoading ? (
        <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />
      ) : (
        <DataTable
          columns={columns}
          data={apps}
          onRowClick={(a) => navigate(`/service-apps/${a.id}`)}
          emptyMessage="No service apps registered"
        />
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Register Service App">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Display Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="My Backend"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">Service Name</label>
            <input
              value={form.service_name}
              onChange={(e) => setForm((f) => ({ ...f, service_name: e.target.value }))}
              placeholder="my-backend"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
            <p className="mt-1 text-xs text-zinc-600">Lowercase, hyphens only (e.g. my-backend)</p>
          </div>
          {create.isError && (
            <div className="text-xs text-red-400">{(create.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowCreate(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || !form.service_name || create.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              {create.isPending ? "Creating..." : "Create"}
            </button>
          </div>
        </div>
      </Modal>

      <KeyRevealModal
        open={!!revealKey}
        onClose={() => setRevealKey(null)}
        apiKey={revealKey ?? ""}
      />
    </div>
  );
}
