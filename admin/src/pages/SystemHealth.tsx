import { useQuery } from "@tanstack/react-query";
import { getSystemHealth } from "../api/client";

export function SystemHealth() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["system-health"],
    queryFn: getSystemHealth,
    refetchInterval: 30000,
  });

  if (isLoading) return <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />;
  if (error) return <div className="text-red-400 text-sm">Failed to load: {(error as Error).message}</div>;
  if (!data) return null;

  const formatUptime = (seconds: number) => {
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d > 0) return `${d}d ${h}h ${m}m`;
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">System Health</h1>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${data.status === "healthy" ? "bg-emerald-400" : "bg-amber-400"}`} />
          <span className={`text-sm font-medium ${data.status === "healthy" ? "text-emerald-400" : "text-amber-400"}`}>
            {data.status.charAt(0).toUpperCase() + data.status.slice(1)}
          </span>
        </div>
      </div>

      {/* Overview */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
          <div className="text-xs text-zinc-500 mb-1">Uptime</div>
          <div className="text-lg font-semibold tabular-nums">{formatUptime(data.uptime_seconds)}</div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
          <div className="text-xs text-zinc-500 mb-1">Version</div>
          <div className="text-lg font-semibold">{data.version}</div>
        </div>
      </div>

      {/* Dependency checks */}
      <div>
        <h2 className="text-sm font-medium text-zinc-400 mb-3">Dependencies</h2>
        <div className="grid grid-cols-2 gap-4">
          {Object.entries(data.checks).map(([name, check]) => (
            <div key={name} className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium capitalize">{name}</span>
                <div className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${check.status === "ok" ? "bg-emerald-400" : "bg-red-400"}`} />
                  <span className={`text-xs font-medium ${check.status === "ok" ? "text-emerald-400" : "text-red-400"}`}>
                    {check.status === "ok" ? "Connected" : "Error"}
                  </span>
                </div>
              </div>
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs">
                  <span className="text-zinc-500">Latency</span>
                  <span className="text-zinc-300 tabular-nums">{check.latency_ms}ms</span>
                </div>
                {check.error && (
                  <div className="text-xs text-red-400 mt-2 break-all">{check.error}</div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="text-xs text-zinc-600">Auto-refreshes every 30 seconds</div>
    </div>
  );
}
