import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { createOrganization, getOrganizations } from "../api/client";
import type { Organization } from "../types/api";
import { DataTable } from "../components/DataTable";
import { Modal } from "../components/Modal";
import { StatusBadge } from "../components/Badge";

export function Organizations() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ name: "", slug: "" });

  const { data: orgs = [], isLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
  });

  const create = useMutation({
    mutationFn: () => createOrganization({ name: form.name, slug: form.slug }),
    onSuccess: (org: Organization) => {
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
      setShowCreate(false);
      setForm({ name: "", slug: "" });
      toast.success("Organization created");
      navigate(`/organizations/${org.id}`);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const columns = [
    {
      key: "name",
      header: "Name",
      render: (o: Organization) => (
        <span className="font-medium text-sm">
          {o.is_public && <span className="mr-1">🌐</span>}
          {o.name}
          {o.is_public && (
            <span className="ml-2 text-xs text-zinc-500">(public catch-all)</span>
          )}
        </span>
      ),
    },
    {
      key: "slug",
      header: "Slug",
      render: (o: Organization) => (
        <code className="text-xs text-zinc-400 font-mono">{o.slug}</code>
      ),
    },
    {
      key: "domains",
      header: "Domains",
      render: (o: Organization) => (
        <span className="text-sm text-zinc-300">
          {o.is_public ? "—" : o.domain_count}
        </span>
      ),
      className: "w-24",
    },
    {
      key: "enabled",
      header: "Enabled",
      render: (o: Organization) => <StatusBadge active={o.enabled} />,
      className: "w-28",
    },
    {
      key: "users",
      header: "Users",
      render: (o: Organization) => (
        <span className="text-sm text-zinc-300">{o.user_count}</span>
      ),
      className: "w-20",
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Organizations</h1>
          <p className="text-sm text-zinc-500">
            Email-domain tenancy. The public org is the catch-all for unclaimed
            domains; its status is the public sign-in switch.
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white transition-colors"
        >
          New org
        </button>
      </div>

      {isLoading ? (
        <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />
      ) : (
        <DataTable
          columns={columns}
          data={orgs}
          onRowClick={(o) => navigate(`/organizations/${o.id}`)}
          emptyMessage="No organizations"
        />
      )}

      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="New Organization"
      >
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Display Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Texas A&M University"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">
              Slug (in the token's org claim — immutable)
            </label>
            <input
              value={form.slug}
              onChange={(e) =>
                setForm((f) => ({ ...f, slug: e.target.value }))
              }
              placeholder="tamu"
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
            <p className="mt-1 text-xs text-zinc-600">
              Lowercase letters, digits, and hyphens; min 2 characters.
            </p>
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
