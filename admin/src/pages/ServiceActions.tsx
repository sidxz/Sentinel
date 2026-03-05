import { useQuery } from "@tanstack/react-query";
import { getServiceActions } from "../api/client";
import type { ServiceAction } from "../types/api";

export function ServiceActions() {
  const { data: actions = [], isLoading } = useQuery({
    queryKey: ["service-actions"],
    queryFn: () => getServiceActions(),
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
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/50">
              {grouped[svc].map((a) => (
                <tr key={a.id} className="hover:bg-zinc-800/30">
                  <td className="px-4 py-2 font-mono text-xs text-zinc-300">{a.action}</td>
                  <td className="px-4 py-2 text-zinc-500">{a.description || "—"}</td>
                  <td className="px-4 py-2 text-xs text-zinc-600">
                    {new Date(a.created_at).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
