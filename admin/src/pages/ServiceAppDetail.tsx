import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import {
  deleteServiceApp,
  getServiceApp,
  purgeServicePermissions,
  rotateServiceAppKey,
  updateServiceApp,
} from "../api/client";
import { StatusBadge } from "../components/Badge";
import { ConfirmModal } from "../components/ConfirmModal";
import { Modal } from "../components/Modal";
import type { ServiceAppCreateResponse } from "../types/api";

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
    <Modal open={open} onClose={onClose} title="New API Key">
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

export function ServiceAppDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showEdit, setShowEdit] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [showRotate, setShowRotate] = useState(false);
  const [showPurge, setShowPurge] = useState(false);
  const [deleteName, setDeleteName] = useState("");
  const [purgeName, setPurgeName] = useState("");
  const [editForm, setEditForm] = useState({ name: "", is_active: true, allowed_origins: "" });
  const [revealKey, setRevealKey] = useState<string | null>(null);

  const { data: app } = useQuery({
    queryKey: ["service-app", id],
    queryFn: () => getServiceApp(id!),
    enabled: !!id,
  });

  const update = useMutation({
    mutationFn: () =>
      updateServiceApp(id!, {
        name: editForm.name || undefined,
        is_active: editForm.is_active,
        allowed_origins: editForm.allowed_origins
          ? editForm.allowed_origins.split("\n").map((s) => s.trim()).filter(Boolean)
          : [],
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["service-app", id] });
      queryClient.invalidateQueries({ queryKey: ["service-apps"] });
      setShowEdit(false);
      toast.success("Service app updated");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const rotate = useMutation({
    mutationFn: () => rotateServiceAppKey(id!),
    onSuccess: (result: ServiceAppCreateResponse) => {
      queryClient.invalidateQueries({ queryKey: ["service-app", id] });
      queryClient.invalidateQueries({ queryKey: ["service-apps"] });
      setShowRotate(false);
      toast.success("Key rotated");
      setRevealKey(result.api_key);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const remove = useMutation({
    mutationFn: () => deleteServiceApp(id!),
    onSuccess: () => {
      setShowDelete(false);
      queryClient.invalidateQueries({ queryKey: ["service-apps"] });
      toast.success("Service app and all its permissions deleted");
      navigate("/service-apps");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const purge = useMutation({
    mutationFn: () => purgeServicePermissions(app!.service_name),
    onSuccess: (data) => {
      setShowPurge(false);
      setPurgeName("");
      queryClient.invalidateQueries({ queryKey: ["admin-permissions"] });
      toast.success(`Purged ${data.deleted_count} permission(s) for ${app!.service_name}`);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const openEdit = () => {
    if (app) {
      setEditForm({
        name: app.name,
        is_active: app.is_active,
        allowed_origins: (app.allowed_origins || []).join("\n"),
      });
    }
    setShowEdit(true);
  };

  if (!app) return <div className="animate-pulse h-64 bg-zinc-800/30 rounded-lg" />;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-zinc-500">
        <Link to="/service-apps" className="hover:text-zinc-300">Service Apps</Link>
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
            <div className="mt-2 space-y-1">
              <div className="text-xs text-zinc-500">
                Service: <code className="text-zinc-400 font-mono">{app.service_name}</code>
              </div>
              <div className="text-xs text-zinc-500">
                Key: <code className="text-zinc-400 font-mono">{app.key_prefix}</code>
              </div>
              <div className="text-xs text-zinc-500">
                Last used: {app.last_used_at ? new Date(app.last_used_at).toLocaleString() : "Never"}
              </div>
              <div className="text-xs text-zinc-500">
                Created {new Date(app.created_at).toLocaleDateString()}
              </div>
              {app.allowed_origins && app.allowed_origins.length > 0 && (
                <div className="text-xs text-zinc-500">
                  Origins:{" "}
                  {app.allowed_origins.map((o: string, i: number) => (
                    <code key={i} className="text-zinc-400 font-mono">
                      {o}{i < app.allowed_origins.length - 1 ? ", " : ""}
                    </code>
                  ))}
                </div>
              )}
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
              onClick={() => setShowRotate(true)}
              className="px-3 py-1.5 rounded text-xs font-medium bg-amber-500/10 text-amber-400 hover:bg-amber-500/20 ring-1 ring-amber-500/20 transition-colors"
            >
              Rotate Key
            </button>
            <button
              onClick={() => { setShowPurge(true); setPurgeName(""); }}
              className="px-3 py-1.5 rounded text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 ring-1 ring-red-500/20 transition-colors"
            >
              Purge Permissions
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

      {/* Edit modal */}
      <Modal open={showEdit} onClose={() => setShowEdit(false)} title="Edit Service App">
        <div className="space-y-3">
          <div>
            <label className="text-xs text-zinc-500">Name</label>
            <input
              value={editForm.name}
              onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 focus:outline-none focus:ring-1 focus:ring-zinc-600"
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
          <div>
            <label className="text-xs text-zinc-500">Allowed Origins</label>
            <textarea
              value={editForm.allowed_origins}
              onChange={(e) => setEditForm((f) => ({ ...f, allowed_origins: e.target.value }))}
              placeholder={"https://app.example.com\nhttps://staging.example.com"}
              rows={3}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 font-mono placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
            <p className="mt-1 text-xs text-zinc-600">One origin per line. Required for browser-direct authz mode.</p>
          </div>
          {update.isError && (
            <div className="text-xs text-red-400">{(update.error as Error).message}</div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={() => setShowEdit(false)} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">Cancel</button>
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

      {/* Rotate key confirmation */}
      <ConfirmModal
        open={showRotate}
        onClose={() => setShowRotate(false)}
        onConfirm={() => rotate.mutate()}
        title="Rotate API Key"
        message={`This will invalidate the current key for "${app.name}". Any services using the old key will stop working immediately.`}
        confirmLabel="Rotate Key"
        danger
        isPending={rotate.isPending}
      />

      {/* Delete confirmation */}
      <ConfirmModal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        onConfirm={() => remove.mutate()}
        title="Delete Service App"
        message={`This will permanently delete "${app.name}", invalidate its API key, and purge all stored permissions for service "${app.service_name}". Type the service name to confirm.`}
        confirmLabel="Delete Service App"
        danger
        isPending={remove.isPending}
        confirmInput={app.service_name}
        confirmInputValue={deleteName}
        onConfirmInputChange={setDeleteName}
      />

      {/* Purge permissions confirmation */}
      <ConfirmModal
        open={showPurge}
        onClose={() => setShowPurge(false)}
        onConfirm={() => purge.mutate()}
        title="Purge All Permissions"
        message={`This will delete ALL resource permissions and shares for service "${app.service_name}". This cannot be undone. Type the service name to confirm.`}
        confirmLabel="Purge Permissions"
        danger
        isPending={purge.isPending}
        confirmInput={app.service_name}
        confirmInputValue={purgeName}
        onConfirmInputChange={setPurgeName}
      />

      {/* Key reveal */}
      <KeyRevealModal
        open={!!revealKey}
        onClose={() => setRevealKey(null)}
        apiKey={revealKey ?? ""}
      />
    </div>
  );
}
