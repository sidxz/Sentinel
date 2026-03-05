import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { deleteServiceAction, getServiceActions } from "../api/client";
import { ConfirmModal } from "../components/ConfirmModal";
import { useState } from "react";
import type { ServiceAction } from "../types/api";

export function ServiceActions() {
  const queryClient = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<ServiceAction | null>(null);

  const { data: actions = [], isLoading } = useQuery({
    queryKey: ["service-actions"],
    queryFn: () => getServiceActions(),
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteServiceAction(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["service-actions"] });
      setDeleteTarget(null);
      toast.success("Action deleted");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  if (isLoading) return <div className="animate-pulse h-64 bg-zinc-800/30 rounded-lg" />;

  // Group by service_name
  const grouped = actions.reduce<Record<string, ServiceAction[]>>((acc, a) => {
    (acc[a.service_name] ??= []).push(a);
    return acc;
  }, {});

  const serviceNames = Object.keys(grouped).sort();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">Service Actions</h1>
        <p className="text-sm text-zinc-500 mt-1">
          Actions registered by services for RBAC. {actions.length} total across {serviceNames.length} service{serviceNames.length !== 1 ? "s" : ""}.
        </p>
      </div>

      {serviceNames.length === 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 px-4 py-8 text-center text-sm text-zinc-500">
          No service actions registered yet
        </div>
      )}

      {serviceNames.map((svc) => (
        <div key={svc} className="rounded-lg border border-zinc-800 bg-zinc-900">
          <div className="px-4 py-3 border-b border-zinc-800">
            <h2 className="text-sm font-medium">{svc}</h2>
            <div className="text-xs text-zinc-500">{grouped[svc].length} actions</div>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-zinc-500 border-b border-zinc-800/50">
                <th className="px-4 py-2 font-medium">Action</th>
                <th className="px-4 py-2 font-medium">Description</th>
                <th className="px-4 py-2 font-medium">Registered</th>
                <th className="px-4 py-2 font-medium w-16" />
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {grouped[svc].map((a) => (
                <tr key={a.id} className="hover:bg-zinc-800/30 group">
                  <td className="px-4 py-2 font-mono text-xs text-zinc-300">{a.action}</td>
                  <td className="px-4 py-2 text-zinc-500">{a.description || "—"}</td>
                  <td className="px-4 py-2 text-xs text-zinc-600">
                    {new Date(a.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => setDeleteTarget(a)}
                      className="text-xs text-red-400/60 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      <ConfirmModal
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && remove.mutate(deleteTarget.id)}
        title="Delete Service Action"
        message={`Delete "${deleteTarget?.action}" from ${deleteTarget?.service_name}? This will also remove it from any roles using it.`}
        confirmLabel="Delete"
        danger
        isPending={remove.isPending}
      />
    </div>
  );
}
