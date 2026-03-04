import { useState } from "react";
import { VisibilityBadge } from "../components/Badge";
import type { ResourcePermission } from "../types/api";

const BASE = "/api";

export function Permissions() {
  const [serviceName, setServiceName] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [resourceId, setResourceId] = useState("");
  const [result, setResult] = useState<ResourcePermission | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const lookup = async () => {
    if (!serviceName || !resourceType || !resourceId) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(
        `${BASE}/permissions/resource/${serviceName}/${resourceType}/${resourceId}`
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${res.status}`);
      }
      setResult(await res.json());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Permissions Browser</h1>

      {/* Lookup form */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 space-y-4">
        <div className="text-sm text-zinc-400">Look up a resource's permission record and shares</div>
        <div className="grid grid-cols-3 gap-3">
          <input
            value={serviceName}
            onChange={(e) => setServiceName(e.target.value)}
            placeholder="service_name (e.g. docu-store)"
            className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <input
            value={resourceType}
            onChange={(e) => setResourceType(e.target.value)}
            placeholder="resource_type (e.g. artifact)"
            className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
          <input
            value={resourceId}
            onChange={(e) => setResourceId(e.target.value)}
            placeholder="resource_id (UUID)"
            className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
          />
        </div>
        <button
          onClick={lookup}
          disabled={loading || !serviceName || !resourceType || !resourceId}
          className="px-4 py-2 rounded text-sm font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50 transition-colors"
        >
          {loading ? "Looking up..." : "Lookup"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 space-y-4">
          <div className="flex items-center gap-3">
            <h3 className="text-sm font-semibold">Resource Permission</h3>
            <VisibilityBadge visibility={result.visibility} />
          </div>

          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            <div>
              <dt className="text-zinc-500 text-xs">Service</dt>
              <dd className="font-mono">{result.service_name}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 text-xs">Type</dt>
              <dd className="font-mono">{result.resource_type}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 text-xs">Resource ID</dt>
              <dd className="font-mono text-xs">{result.resource_id}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 text-xs">Owner ID</dt>
              <dd className="font-mono text-xs">{result.owner_id}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 text-xs">Workspace ID</dt>
              <dd className="font-mono text-xs">{result.workspace_id}</dd>
            </div>
            <div>
              <dt className="text-zinc-500 text-xs">Created</dt>
              <dd>{new Date(result.created_at).toLocaleString()}</dd>
            </div>
          </dl>

          {/* Shares */}
          <div>
            <h4 className="text-sm font-medium text-zinc-400 mb-2">
              Shares ({result.shares.length})
            </h4>
            {result.shares.length === 0 ? (
              <div className="text-xs text-zinc-500">No explicit shares</div>
            ) : (
              <div className="rounded border border-zinc-800 divide-y divide-zinc-800/50">
                {result.shares.map((s) => (
                  <div key={s.id} className="flex items-center justify-between px-3 py-2 text-sm">
                    <div>
                      <span className="capitalize text-zinc-400">{s.grantee_type}</span>{" "}
                      <span className="font-mono text-xs">{s.grantee_id}</span>
                    </div>
                    <span className={`text-xs font-medium ${s.permission === "edit" ? "text-blue-400" : "text-zinc-400"}`}>
                      {s.permission}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!result && !error && (
        <div className="text-center py-16 text-zinc-600 text-sm">
          Enter a service name, resource type, and resource ID to look up its permissions
        </div>
      )}
    </div>
  );
}
