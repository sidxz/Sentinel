import { useQuery } from "@tanstack/react-query";
import { getSystemSettings } from "../api/client";

export function Settings() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["system-settings"],
    queryFn: getSystemSettings,
  });

  if (isLoading) return <div className="h-64 bg-zinc-800/30 rounded-lg animate-pulse" />;
  if (error) return <div className="text-red-400 text-sm">Failed to load: {(error as Error).message}</div>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Settings</h1>

      {/* Service */}
      <Section title="Service">
        <KV label="Base URL" value={data.service.base_url} />
        <KV label="Frontend URL" value={data.service.frontend_url} />
        <KV label="Admin URL" value={data.service.admin_url} />
      </Section>

      {/* OAuth Providers */}
      <Section title="OAuth Providers">
        {data.oauth_providers.map((p) => (
          <KV
            key={p.name}
            label={p.name.charAt(0).toUpperCase() + p.name.slice(1)}
            value={p.configured ? "Configured" : "Not configured"}
            valueClass={p.configured ? "text-emerald-400" : "text-zinc-500"}
          />
        ))}
      </Section>

      {/* JWT */}
      <Section title="JWT">
        <KV label="Algorithm" value={data.jwt.algorithm} />
        <KV label="Access Token TTL" value={`${data.jwt.access_token_expire_minutes} minutes`} />
        <KV label="Refresh Token TTL" value={`${data.jwt.refresh_token_expire_days} days`} />
        <KV label="Denylist Entries" value={String(data.jwt.denylist_count)} />
        {data.jwt.public_key_preview && (
          <div className="px-4 py-2.5 flex gap-3">
            <span className="text-xs text-zinc-500 w-40 shrink-0">Public Key</span>
            <span className="text-xs text-zinc-400 font-mono truncate">{data.jwt.public_key_preview}</span>
          </div>
        )}
      </Section>

      {/* Security */}
      <Section title="Security">
        <KV
          label="Cookie Secure"
          value={data.security.cookie_secure ? "Enabled" : "Disabled"}
          valueClass={data.security.cookie_secure ? "text-emerald-400" : "text-amber-400"}
        />
        <KV
          label="Session Secret"
          value={data.security.session_secret_configured ? "Configured" : "Using default (insecure)"}
          valueClass={data.security.session_secret_configured ? "text-emerald-400" : "text-red-400"}
        />
        <KV label="Allowed Hosts" value={data.security.allowed_hosts.join(", ")} />
        <KV label="CORS Origins" value={data.security.cors_origins.join(", ")} />
        <KV label="Admin Emails" value={data.security.admin_emails.join(", ") || "None"} />
      </Section>

      {/* Rate Limits */}
      <Section title="Rate Limits">
        {data.rate_limits.map((rl) => (
          <KV key={rl.endpoint} label={rl.endpoint} value={rl.limit} />
        ))}
      </Section>

      {/* Service Keys */}
      <Section title="Service API Keys">
        {data.service_keys.length === 0 ? (
          <div className="px-4 py-3 text-xs text-zinc-500">No service keys configured</div>
        ) : (
          data.service_keys.map((sk) => (
            <KV key={sk.name} label={sk.name} value={sk.preview} mono />
          ))
        )}
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-sm font-medium text-zinc-400 mb-2">{title}</h2>
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 divide-y divide-zinc-800/50">
        {children}
      </div>
    </div>
  );
}

function KV({
  label,
  value,
  valueClass,
  mono,
}: {
  label: string;
  value: string;
  valueClass?: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center px-4 py-2.5">
      <span className="text-xs text-zinc-500 w-40 shrink-0">{label}</span>
      <span className={`text-xs ${mono ? "font-mono" : ""} ${valueClass ?? "text-zinc-300"} truncate`}>
        {value}
      </span>
    </div>
  );
}
