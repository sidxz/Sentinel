import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  addRealmMember,
  deleteRealm,
  getRealm,
  getRealmMembers,
  getServiceApps,
  removeRealmMember,
  updateRealm,
} from "../api/client";
import type { RealmMember } from "../types/api";
import { ConfirmModal } from "../components/ConfirmModal";
import { Modal } from "../components/Modal";
import { StatusBadge } from "../components/Badge";

export function RealmDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [showEdit, setShowEdit] = useState(false);
  const [editForm, setEditForm] = useState({
    name: "",
    m2m_ttl_s: "300",
    is_active: true,
  });
  const [showDelete, setShowDelete] = useState(false);
  const [deleteSlug, setDeleteSlug] = useState("");
  const [selectedApp, setSelectedApp] = useState("");

  const {
    data: realm,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["realm", id],
    queryFn: () => getRealm(id!),
    enabled: !!id,
  });

  const { data: members = [] } = useQuery({
    queryKey: ["realm-members", id],
    queryFn: () => getRealmMembers(id!),
    enabled: !!id,
  });

  const { data: allApps = [] } = useQuery({
    queryKey: ["service-apps"],
    queryFn: getServiceApps,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["realm", id] });
    queryClient.invalidateQueries({ queryKey: ["realm-members", id] });
    queryClient.invalidateQueries({ queryKey: ["realms"] });
    queryClient.invalidateQueries({ queryKey: ["service-apps"] });
  };

  const update = useMutation({
    mutationFn: () =>
      updateRealm(id!, {
        name: editForm.name || undefined,
        m2m_ttl_s: Number(editForm.m2m_ttl_s),
        is_active: editForm.is_active,
      }),
    onSuccess: () => {
      invalidate();
      setShowEdit(false);
      toast.success("Realm updated");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const addMember = useMutation({
    mutationFn: (serviceAppId: string) => addRealmMember(id!, serviceAppId),
    onSuccess: () => {
      invalidate();
      setSelectedApp("");
      toast.success("Service added to realm");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const removeMember = useMutation({
    mutationFn: (serviceAppId: string) => removeRealmMember(id!, serviceAppId),
    onSuccess: () => {
      invalidate();
      toast.success("Service removed from realm");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const remove = useMutation({
    mutationFn: () => deleteRealm(id!),
    onSuccess: () => {
      setShowDelete(false);
      invalidate();
      toast.success("Realm deleted");
      navigate("/realms");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const openEdit = () => {
    if (realm) {
      setEditForm({
        name: realm.name,
        m2m_ttl_s: String(realm.m2m_ttl_s),
        is_active: realm.is_active,
      });
    }
    setShowEdit(true);
  };

  if (isLoading) {
    return <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />;
  }

  if (isError || !realm) {
    return (
      <div className="space-y-3 max-w-3xl">
        <Link to="/realms" className="text-sm text-zinc-500 hover:text-zinc-300">
          ← Realms
        </Link>
        <div className="border border-zinc-800 rounded-lg p-6 text-center">
          <p className="text-sm text-zinc-300">
            {(error as Error)?.message ?? "Realm not found."}
          </p>
        </div>
      </div>
    );
  }

  // A service belongs to at most one realm — only standalone apps are candidates.
  // ponytail: candidate pre-add has_grants warning skipped — needs
  // ServiceAppResponse.has_grants (backend). Member-row badge covers it post-add.
  const candidates = allApps.filter((a) => a.realm_id == null);

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <Link to="/realms" className="hover:text-zinc-300">
          Realms
        </Link>
        <span>/</span>
        <span className="text-zinc-200">{realm.name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-lg font-semibold">{realm.name}</h1>
          <code className="text-xs text-zinc-500 font-mono">{realm.slug}</code>
          <p className="mt-1 text-xs text-zinc-500">
            m2m token TTL: {realm.m2m_ttl_s}s
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge active={realm.is_active} />
          <button
            onClick={openEdit}
            className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white transition-colors"
          >
            Edit
          </button>
        </div>
      </div>

      {/* Members */}
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-zinc-300">Member services</h2>
        {members.length === 0 ? (
          <p className="text-sm text-zinc-500">
            No services yet — add a standalone service below. Members share this
            realm's permission scope.
          </p>
        ) : (
          <ul className="space-y-1">
            {members.map((m: RealmMember) => (
              <li
                key={m.id}
                className="flex items-center justify-between border border-zinc-800 rounded-md px-3 py-2"
              >
                <span className="text-sm">
                  <span className="text-zinc-200">{m.name}</span>
                  <code className="ml-2 text-xs text-zinc-500 font-mono">
                    {m.service_name}
                  </code>
                  {m.has_grants && (
                    <span
                      className="ml-2 text-xs text-amber-400"
                      title="This service has its own permission grants, which are NOT visible under the realm scope."
                    >
                      ⚠ has own grants
                    </span>
                  )}
                </span>
                <button
                  onClick={() => removeMember.mutate(m.id)}
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
            <label className="text-xs text-zinc-500">Add a standalone service</label>
            <select
              value={selectedApp}
              onChange={(e) => setSelectedApp(e.target.value)}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            >
              <option value="">Select a service…</option>
              {candidates.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.service_name})
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() => {
              if (selectedApp) addMember.mutate(selectedApp);
            }}
            disabled={!selectedApp || addMember.isPending}
            className="px-3 py-2 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50 transition-colors"
          >
            Add
          </button>
        </div>
      </section>

      {/* Danger zone */}
      <section className="space-y-2 border-t border-zinc-800 pt-4">
        <h2 className="text-sm font-semibold text-red-400">Danger zone</h2>
        <p className="text-sm text-zinc-500">
          Deleting a realm un-assigns its member services (their{" "}
          <code className="font-mono">realm_id</code> is cleared). Permissions
          written under the realm scope are NOT deleted.
        </p>
        <button
          onClick={() => {
            setDeleteSlug("");
            setShowDelete(true);
          }}
          className="px-3 py-1.5 rounded text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 ring-1 ring-red-500/20 transition-colors"
        >
          Delete realm
        </button>
      </section>

      {/* Edit modal */}
      <Modal open={showEdit} onClose={() => setShowEdit(false)} title="Edit Realm">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Name</label>
            <input
              value={editForm.name}
              onChange={(e) =>
                setEditForm((f) => ({ ...f, name: e.target.value }))
              }
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">m2m token TTL (seconds)</label>
            <input
              type="number"
              min={30}
              max={3600}
              value={editForm.m2m_ttl_s}
              onChange={(e) =>
                setEditForm((f) => ({ ...f, m2m_ttl_s: e.target.value }))
              }
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
            <p className="mt-1 text-xs text-zinc-600">Between 30 and 3600.</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="realm_is_active"
              checked={editForm.is_active}
              onChange={(e) =>
                setEditForm((f) => ({ ...f, is_active: e.target.checked }))
              }
              className="rounded border-zinc-600 bg-zinc-800 text-zinc-300"
            />
            <label htmlFor="realm_is_active" className="text-xs text-zinc-400">
              Active
            </label>
          </div>
          <p className="text-xs text-zinc-600">
            Slug is immutable and cannot be changed.
          </p>
          {update.isError && (
            <div className="text-xs text-red-400">
              {(update.error as Error).message}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={() => setShowEdit(false)}
              className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200"
            >
              Cancel
            </button>
            <button
              onClick={() => update.mutate()}
              disabled={update.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <ConfirmModal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={() => remove.mutate()}
        title="Delete Realm"
        message={`This permanently deletes "${realm.name}" and clears realm_id on its member services. Type the slug to confirm.`}
        confirmLabel="Delete Realm"
        danger
        isPending={remove.isPending}
        confirmInput={realm.slug}
        confirmInputValue={deleteSlug}
        onConfirmInputChange={setDeleteSlug}
      />
    </div>
  );
}
