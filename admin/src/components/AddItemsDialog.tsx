import { useEffect, useMemo, useState, type ReactNode } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

export type PickerItem = {
  id: string;
  label: string;
  sublabel?: string;
  group?: string;
  disabled?: boolean;
  disabledReason?: string;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  items: PickerItem[];
  /** Present = server-search mode: debounced query is pushed up, parent re-renders items. */
  onSearch?: (q: string) => void;
  isLoading?: boolean;
  /** Throw to keep the dialog open (caller surfaces its own error toast). */
  onAdd: (ids: string[]) => Promise<void>;
  addLabel: (n: number) => string;
  /** Rendered left of Cancel/Add — e.g. the batch role select. */
  footer?: ReactNode;
};

export function AddItemsDialog({
  open,
  onOpenChange,
  title,
  items,
  onSearch,
  isLoading,
  onAdd,
  addLabel,
  footer,
}: Props) {
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pending, setPending] = useState(false);

  // Fresh state every time the dialog opens (guards stale-picker bugs, cf. 563e53f).
  useEffect(() => {
    if (open) {
      setQuery("");
      setSelected(new Set());
    }
  }, [open]);

  // Server mode: debounce query up to the parent.
  useEffect(() => {
    if (!onSearch) return;
    const t = setTimeout(() => onSearch(query), 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  const visible = useMemo(() => {
    if (onSearch) return items; // server already filtered
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((i) =>
      [i.label, i.sublabel, i.group].some((s) => s?.toLowerCase().includes(q)),
    );
  }, [items, query, onSearch]);

  const groups = useMemo(() => {
    const m = new Map<string, PickerItem[]>();
    for (const i of visible) {
      const g = i.group ?? "";
      if (!m.has(g)) m.set(g, []);
      m.get(g)!.push(i);
    }
    return [...m.entries()];
  }, [visible]);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const toggleGroup = (groupItems: PickerItem[]) => {
    const enabled = groupItems.filter((i) => !i.disabled);
    const allIn = enabled.length > 0 && enabled.every((i) => selected.has(i.id));
    setSelected((prev) => {
      const next = new Set(prev);
      for (const i of enabled) {
        if (allIn) next.delete(i.id);
        else next.add(i.id);
      }
      return next;
    });
  };

  const handleAdd = async () => {
    setPending(true);
    try {
      await onAdd([...selected]);
      onOpenChange(false);
    } catch {
      // caller toasted; keep dialog open
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>
        <Input
          autoFocus
          placeholder="Search…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="max-h-[50vh] overflow-y-auto rounded-md border border-border">
          {isLoading &&
            [0, 1, 2].map((n) => (
              <div key={n} className="px-3 py-2.5">
                <div className="h-4 w-2/3 rounded bg-muted animate-pulse" />
              </div>
            ))}
          {!isLoading && visible.length === 0 && (
            <div className="px-3 py-8 text-center text-sm text-muted-foreground">
              {items.length === 0 && !query.trim()
                ? "Nothing left to add"
                : "No matches"}
            </div>
          )}
          {!isLoading &&
            groups.map(([group, groupItems]) => {
              const enabled = groupItems.filter((i) => !i.disabled);
              const allIn =
                enabled.length > 0 && enabled.every((i) => selected.has(i.id));
              return (
                <div key={group || "__flat__"}>
                  {group && (
                    <div className="sticky top-0 z-10 flex items-center justify-between bg-muted px-3 py-1.5">
                      <span className="font-mono text-xs font-medium text-muted-foreground">
                        {group}
                      </span>
                      <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
                        select all
                        <Checkbox
                          checked={allIn}
                          disabled={enabled.length === 0}
                          onCheckedChange={() => toggleGroup(groupItems)}
                        />
                      </label>
                    </div>
                  )}
                  {groupItems.map((item) => (
                    <label
                      key={item.id}
                      className={`flex items-center gap-2.5 px-3 py-2 ${
                        item.disabled
                          ? "opacity-50"
                          : "cursor-pointer hover:bg-muted/50"
                      }`}
                    >
                      <Checkbox
                        checked={selected.has(item.id)}
                        disabled={item.disabled}
                        onCheckedChange={() => toggle(item.id)}
                      />
                      <span className="min-w-0 flex-1 text-sm">
                        <span className="text-foreground">{item.label}</span>
                        {item.sublabel && (
                          <span className="ml-2 text-xs text-muted-foreground">
                            {item.sublabel}
                          </span>
                        )}
                      </span>
                      {item.disabled && item.disabledReason && (
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {item.disabledReason}
                        </span>
                      )}
                    </label>
                  ))}
                </div>
              );
            })}
        </div>
        <DialogFooter className="items-center gap-2 sm:justify-between">
          <span className="text-xs text-muted-foreground">
            {selected.size} selected
          </span>
          <div className="flex items-center gap-2">
            {footer}
            <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={selected.size === 0 || pending}
              onClick={handleAdd}
            >
              {addLabel(selected.size)}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Run one call per item, then toast a single summary. Never throws. */
export async function batchAdd(
  selected: PickerItem[],
  call: (item: PickerItem) => Promise<unknown>,
  noun: string,
): Promise<void> {
  const results = await Promise.allSettled(selected.map((i) => call(i)));
  const failures = results
    .map((result, idx) => ({ result, item: selected[idx] }))
    .filter(
      (x): x is { result: PromiseRejectedResult; item: PickerItem } =>
        x.result.status === "rejected",
    );
  const added = selected.length - failures.length;
  if (failures.length === 0) {
    toast.success(`Added ${added} ${noun}${added === 1 ? "" : "s"}`);
  } else {
    toast.error(
      `Added ${added}, ${failures.length} failed: ${failures
        .map(
          (f) =>
            `${f.item.label} — ${
              f.result.reason instanceof Error
                ? f.result.reason.message
                : "error"
            }`,
        )
        .join("; ")}`,
    );
  }
}
