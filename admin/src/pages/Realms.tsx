import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { createRealm, getRealms } from "../api/client";
import type { Realm } from "../types/api";
import { DataTable } from "../components/DataTable";
import { Modal } from "../components/Modal";
import { StatusBadge } from "../components/Badge";

export function Realms() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "", m2m_ttl_s: "300" });

  const { data: realms = [], isLoading } = useQuery({
    queryKey: ["realms"],
    queryFn: getRealms,
  });

  const create = useMutation({
    mutationFn: () =>
      createRealm({
        name: form.name,
        slug: form.slug,
        m2m_ttl_s: Number(form.m2m_ttl_s),
      }),
    onSuccess: (realm: Realm) => {
      queryClient.invalidateQueries({ queryKey: ["realms"] });
      setShowCreate(false);
      setForm({ name: "", slug: "", m2m_ttl_s: "300" });
      toast.success("Realm created");
      navigate(`/realms/${realm.id}`);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const columns = [
    {
      key: "name",
      header: "Name",
      render: (r: Realm) => <span className="font-medium text-sm">{r.name}</span>,
    },
    {
      key: "slug",
      header: "Slug",
      render: (r: Realm) => (
        <code className="text-xs text-zinc-400 font-mono">{r.slug}</code>
      ),
    },
    {
      key: "m2m_ttl_s",
      header: "m2m TTL",
      render: (r: Realm) => (
        <span className="text-sm text-zinc-300">{r.m2m_ttl_s}s</span>
      ),
      className: "w-24",
    },
    {
      key: "is_active",
      header: "Active",
      render: (r: Realm) => <StatusBadge active={r.is_active} />,
      className: "w-28",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Realms</h1>
          <p className="text-sm text-zinc-500">
            Trusted app groups that share one permission scope. Member services
            read and write permissions under the realm slug, and the realm mints
            no-user (m2m) tokens for them.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white transition-colors"
        >
          New realm
        </button>
      </div>

      {isLoading ? (
        <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />
      ) : (
        <DataTable
          columns={columns}
          data={realms}
          onRowClick={(r) => navigate(`/realms/${r.id}`)}
          emptyMessage="No realms"
        />
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="New Realm">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Display Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Acme Suite"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">
              Slug (the shared permission scope — immutable)
            </label>
            <input
              value={form.slug}
              onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
              placeholder="acme-suite"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
            <p className="mt-1 text-xs text-zinc-600">
              Starts with a letter; lowercase letters, digits, and hyphens.
            </p>
          </div>
          <div>
            <label className="text-xs text-zinc-500">m2m token TTL (seconds)</label>
            <input
              type="number"
              min={30}
              max={3600}
              value={form.m2m_ttl_s}
              onChange={(e) =>
                setForm((f) => ({ ...f, m2m_ttl_s: e.target.value }))
              }
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
            <p className="mt-1 text-xs text-zinc-600">Between 30 and 3600. Default 300.</p>
          </div>
          {create.isError && (
            <div className="text-xs text-red-400">
              {(create.error as Error).message}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setShowCreate(false)}
              className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </button>
            <button
              onClick={() => create.mutate()}
              disabled={!form.name || !form.slug || create.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50 transition-colors"
            >
              {create.isPending ? "Creating..." : "Create"}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
