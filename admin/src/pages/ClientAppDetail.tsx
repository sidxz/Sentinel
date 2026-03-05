import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  deleteClientApp,
  getClientApp,
  updateClientApp,
} from "../api/client";
import { StatusBadge } from "../components/Badge";
import { ConfirmModal } from "../components/ConfirmModal";
import { Modal } from "../components/Modal";

export function ClientAppDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [showDeactivate, setShowDeactivate] = useState(false);
  const [revokeOnDeactivate, setRevokeOnDeactivate] = useState(false);
  const [deleteName, setDeleteName] = useState("");
  const [editForm, setEditForm] = useState({ name: "", redirect_uris: "", is_active: true });

  const { data: app } = useQuery({
    queryKey: ["client-app", id],
    queryFn: () => getClientApp(id!),
    enabled: !!id,
  });

  const update = useMutation({
    mutationFn: (opts?: { revoke_sessions?: boolean }) =>
      updateClientApp(id!, {
        name: editForm.name || undefined,
        redirect_uris: editForm.redirect_uris
          .split("\n")
          .map((u) => u.trim())
          .filter(Boolean),
        is_active: editForm.is_active,
        ...(opts?.revoke_sessions ? { revoke_sessions: true } : {}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["client-app", id] });
      queryClient.invalidateQueries({ queryKey: ["client-apps"] });
      setShowEdit(false);
      setShowDeactivate(false);
      toast.success("App updated");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const remove = useMutation({
    mutationFn: () => deleteClientApp(id!),
    onSuccess: () => {
      setShowDelete(false);
      queryClient.invalidateQueries({ queryKey: ["client-apps"] });
      toast.success("App deleted");
      navigate("/client-apps");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const openEdit = () => {
    if (app) {
      setEditForm({
        name: app.name,
        redirect_uris: app.redirect_uris.join("\n"),
        is_active: app.is_active,
      });
    }
    setShowEdit(true);
  };

  if (!app) return <div className="animate-pulse h-64 bg-zinc-800/30 rounded-lg" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <Link to="/client-apps" className="hover:text-zinc-300">Client Apps</Link>
        <span>/</span>
        <span className="text-zinc-200">{app.name}</span>
      </div>

      {/* Header card */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold">{app.name}</h2>
              <StatusBadge active={app.is_active} />
            </div>
            <div className="text-xs text-zinc-500 mt-2">
              Created {new Date(app.created_at).toLocaleDateString()}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={openEdit}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-800 hover:bg-zinc-700 transition-colors"
            >
              Edit
            </button>
            <button
              onClick={() => { setShowDelete(true); setDeleteName(""); }}
              className="px-3 py-1.5 rounded text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 ring-1 ring-red-500/20 transition-colors"
            >
              Delete
            </button>
          </div>
        </div>
      </div>

      {/* Redirect URIs */}
      <div>
        <h3 className="text-sm font-medium text-zinc-300 mb-2">Redirect URIs</h3>
        <div className="rounded-lg border border-zinc-800 divide-y divide-zinc-800/50">
          {app.redirect_uris.map((uri) => (
            <div key={uri} className="px-4 py-2.5">
              <code className="text-sm text-zinc-400 font-mono">{uri}</code>
            </div>
          ))}
          {app.redirect_uris.length === 0 && (
            <div className="px-4 py-6 text-center text-sm text-zinc-500">No redirect URIs</div>
          )}
        </div>
      </div>

      {/* Edit modal */}
      <Modal open={showEdit} onClose={() => setShowEdit(false)} title="Edit Client App">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Name</label>
            <input
              value={editForm.name}
              onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
          <div>
            <label className="text-xs text-zinc-500">Redirect URIs (one per line)</label>
            <textarea
              value={editForm.redirect_uris}
              onChange={(e) => setEditForm((f) => ({ ...f, redirect_uris: e.target.value }))}
              rows={3}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono focus:outline-none focus:ring-1 focus:ring-zinc-600 resize-none"
            />
          </div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_active"
              checked={editForm.is_active}
              onChange={(e) => setEditForm((f) => ({ ...f, is_active: e.target.checked }))}
              className="rounded border-zinc-600 bg-zinc-800 text-zinc-300"
            />
            <label htmlFor="is_active" className="text-xs text-zinc-400">Active</label>
          </div>
          {update.isError && (
            <div className="text-xs text-red-400">{(update.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowEdit(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
            <button
              onClick={() => {
                if (app && app.is_active && !editForm.is_active) {
                  setShowEdit(false);
                  setRevokeOnDeactivate(false);
                  setShowDeactivate(true);
                } else {
                  update.mutate();
                }
              }}
              disabled={update.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      </Modal>

      {/* Deactivation confirmation */}
      <Modal open={showDeactivate} onClose={() => setShowDeactivate(false)} title="Deactivate Client App">
        <div className="space-y-3">
          <p className="text-sm text-zinc-400">
            This will prevent new logins through <span className="text-zinc-200 font-medium">{app.name}</span>. Users with active sessions can continue until their tokens expire.
          </p>
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={revokeOnDeactivate}
              onChange={(e) => setRevokeOnDeactivate(e.target.checked)}
              className="mt-0.5 rounded border-zinc-600 bg-zinc-800 text-zinc-300"
            />
            <span className="text-sm text-zinc-300">Also revoke all active sessions</span>
          </label>
          {revokeOnDeactivate && (
            <p className="text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded px-3 py-2">
              All users currently signed in through this app will be signed out immediately.
            </p>
          )}
          {update.isError && (
            <div className="text-xs text-red-400">{(update.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => { setShowDeactivate(false); setShowEdit(true); }} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Back</button>
            <button
              onClick={() => update.mutate({ revoke_sessions: revokeOnDeactivate })}
              disabled={update.isPending}
              className="px-3 py-1.5 rounded text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 ring-1 ring-red-500/20 disabled:opacity-50"
            >
              {update.isPending ? "Deactivating..." : "Deactivate"}
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete confirmation */}
      <ConfirmModal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={() => remove.mutate()}
        title="Delete Client App"
        message={`This will permanently delete "${app.name}".`}
        confirmLabel="Delete App"
        danger
        isPending={remove.isPending}
        confirmInput={app.name}
        confirmInputValue={deleteName}
        onConfirmInputChange={setDeleteName}
      />
    </div>
  );
}
