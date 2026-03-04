const ROLE_COLORS: Record<string, string> = {
  owner: "bg-amber-500/15 text-amber-400 ring-amber-500/20",
  admin: "bg-purple-500/15 text-purple-400 ring-purple-500/20",
  editor: "bg-blue-500/15 text-blue-400 ring-blue-500/20",
  viewer: "bg-zinc-500/15 text-zinc-400 ring-zinc-500/20",
};

export function RoleBadge({ role }: { role: string }) {
  const color = ROLE_COLORS[role] ?? ROLE_COLORS.viewer;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ring-1 ring-inset ${color}`}>
      {role}
    </span>
  );
}

export function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ring-1 ring-inset ${
        active
          ? "bg-emerald-500/15 text-emerald-400 ring-emerald-500/20"
          : "bg-red-500/15 text-red-400 ring-red-500/20"
      }`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${active ? "bg-emerald-400" : "bg-red-400"}`} />
      {active ? "Active" : "Inactive"}
    </span>
  );
}

export function VisibilityBadge({ visibility }: { visibility: string }) {
  const isWorkspace = visibility === "workspace";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ring-1 ring-inset ${
        isWorkspace
          ? "bg-blue-500/15 text-blue-400 ring-blue-500/20"
          : "bg-orange-500/15 text-orange-400 ring-orange-500/20"
      }`}
    >
      {visibility}
    </span>
  );
}
