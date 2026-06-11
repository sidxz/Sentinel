import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  addOrgDomain,
  deleteOrganization,
  getOrganization,
  getOrgUsers,
  removeOrgDomain,
  updateOrganization,
} from "../api/client";
import type { OrgDomain } from "../types/api";
import { ConfirmModal } from "../components/ConfirmModal";
import { StatusBadge } from "../components/Badge";

// Named export (codebase convention). Only the OrgDomain type is imported; the
// org object is inferred from getOrganization's return, so the page's
// `OrganizationDetail` name doesn't collide with the `OrganizationDetail` type.
export function OrganizationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [newDomain, setNewDomain] = useState("");
  const [includeSub, setIncludeSub] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [deleteSlug, setDeleteSlug] = useState("");

  const { data: org, isLoading } = useQuery({
    queryKey: ["organization", id],
    queryFn: () => getOrganization(id!),
    enabled: !!id,
  });

  const { data: users = [] } = useQuery({
    queryKey: ["organization-users", id],
    queryFn: () => getOrgUsers(id!),
    enabled: !!id,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["organization", id] });
    queryClient.invalidateQueries({ queryKey: ["organizations"] });
  };

  const toggleEnabled = useMutation({
    mutationFn: () => updateOrganization(id!, { enabled: !org!.enabled }),
    onSuccess: () => {
      invalidate();
      toast.success("Updated");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const addDomain = useMutation({
    mutationFn: () =>
      addOrgDomain(id!, {
        domain: newDomain.trim(),
        include_subdomains: includeSub,
      }),
    onSuccess: () => {
      invalidate();
      setNewDomain("");
      setIncludeSub(false);
      toast.success("Domain added");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const removeDomain = useMutation({
    mutationFn: (domainId: string) => removeOrgDomain(id!, domainId),
    onSuccess: () => {
      invalidate();
      toast.success("Domain removed");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const remove = useMutation({
    mutationFn: () => deleteOrganization(id!),
    onSuccess: () => {
      setShowDelete(false);
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
      toast.success("Organization deleted");
      navigate("/organizations");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  if (isLoading || !org) {
    return <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />;
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <button
        onClick={() => navigate("/organizations")}
        className="text-xs text-zinc-500 hover:text-zinc-300"
      >
        ← Organizations
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold">
            {org.is_public && <span className="mr-1">🌐</span>}
            {org.name}
          </h1>
          <code className="text-xs text-zinc-500 font-mono">{org.slug}</code>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge active={org.enabled} />
          <button
            onClick={() => toggleEnabled.mutate()}
            disabled={toggleEnabled.isPending}
            className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
          >
            {org.enabled
              ? org.is_public
                ? "Disable public sign-in"
                : "Disable"
              : org.is_public
                ? "Enable public sign-in"
                : "Enable"}
          </button>
        </div>
      </div>

      {org.is_public && (
        <p className="text-sm text-zinc-500 border border-zinc-800 rounded-md p-3">
          This is the public catch-all organization for users whose email domain
          is not claimed by any other org. Its <b>Enabled</b> state is the global
          public-sign-in switch. It has no domains and cannot be deleted.
        </p>
      )}

      {/* Domains (real orgs only) */}
      {!org.is_public && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-zinc-300">Email domains</h2>
          {org.domains.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No domains yet — users from this org can't be resolved until you add
              one.
            </p>
          ) : (
            <ul className="space-y-1">
              {org.domains.map((d: OrgDomain) => (
                <li
                  key={d.id}
                  className="flex items-center justify-between border border-zinc-800 rounded-md px-3 py-2"
                >
                  <span className="text-sm">
                    <code className="font-mono text-zinc-200">{d.domain}</code>
                    {d.include_subdomains && (
                      <span className="ml-2 text-xs text-emerald-400">
                        +subdomains
                      </span>
                    )}
                  </span>
                  <button
                    onClick={() => removeDomain.mutate(d.id)}
                    className="text-xs text-red-400 hover:text-red-300"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className="text-xs text-zinc-500">Add domain</label>
              <input
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                placeholder="tamu.edu"
                className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
              />
            </div>
            <label className="flex items-center gap-1.5 text-xs text-zinc-400 pb-2">
              <input
                type="checkbox"
                checked={includeSub}
                onChange={(e) => setIncludeSub(e.target.checked)}
              />
              include subdomains
            </label>
            <button
              onClick={() => addDomain.mutate()}
              disabled={!newDomain.trim() || addDomain.isPending}
              className="px-3 py-2 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </section>
      )}

      {/* Users in org */}
      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-zinc-300">
          Users in this organization ({org.user_count})
        </h2>
        {users.length === 0 ? (
          <p className="text-sm text-zinc-500">No users.</p>
        ) : (
          <ul className="divide-y divide-zinc-800/50 border border-zinc-800 rounded-md">
            {users.map((u) => (
              <li
                key={u.id}
                className="px-3 py-2 flex items-center justify-between"
              >
                <span className="text-sm text-zinc-200">{u.email}</span>
                <span className="text-xs text-zinc-500">{u.name}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Danger zone (real orgs only) */}
      {!org.is_public && (
        <section className="space-y-2 border-t border-zinc-800 pt-4">
          <h2 className="text-sm font-semibold text-red-400">Danger zone</h2>
          <p className="text-sm text-zinc-500">
            Deleting an org un-assigns its users (they fall back to the public org
            on next sign-in) and removes it from every workspace's allow-list.
          </p>
          <button
            onClick={() => setShowDelete(true)}
            className="px-3 py-1.5 rounded text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 ring-1 ring-red-500/20"
          >
            Delete organization
          </button>
        </section>
      )}

      <ConfirmModal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={() => remove.mutate()}
        title="Delete Organization"
        message={`This permanently deletes "${org.name}". Users on its domains fall back to the public org at next sign-in. Type the slug to confirm.`}
        confirmLabel="Delete Organization"
        danger
        isPending={remove.isPending}
        confirmInput={org.slug}
        confirmInputValue={deleteSlug}
        onConfirmInputChange={setDeleteSlug}
      />
    </div>
  );
}
