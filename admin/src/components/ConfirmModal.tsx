import { Modal } from "./Modal";

interface Props {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  isPending?: boolean;
  confirmInput?: string;
  confirmInputValue?: string;
  onConfirmInputChange?: (v: string) => void;
}

export function ConfirmModal({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
  danger = false,
  isPending = false,
  confirmInput,
  confirmInputValue,
  onConfirmInputChange,
}: Props) {
  const disabled = isPending || (confirmInput ? confirmInputValue !== confirmInput : false);

  return (
    <Modal open={open} onClose={onClose} title={title}>
      <div className="space-y-4">
        <p className="text-sm text-zinc-400">{message}</p>
        {confirmInput && (
          <div>
            <label className="text-xs text-zinc-500">
              Type <span className="font-mono text-zinc-300">{confirmInput}</span> to confirm
            </label>
            <input
              value={confirmInputValue ?? ""}
              onChange={(e) => onConfirmInputChange?.(e.target.value)}
              className="mt-1 w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-md text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-600"
            />
          </div>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <button
            onClick={onClose}
            className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={disabled}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-colors disabled:opacity-50 ${
              danger
                ? "bg-red-500/10 text-red-400 hover:bg-red-500/20 ring-1 ring-red-500/20"
                : "bg-zinc-100 text-zinc-900 hover:bg-white"
            }`}
          >
            {isPending ? "..." : confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  );
}
