import { useEffect, useRef } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

export function Modal({ open, onClose, title, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (open) ref.current?.showModal();
    else ref.current?.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      className="backdrop:bg-black/60 bg-zinc-900 border border-zinc-700 rounded-lg p-0 text-zinc-100 w-full max-w-md shadow-2xl"
    >
      <div className="px-5 py-4 border-b border-zinc-800 flex items-center justify-between">
        <h3 className="text-sm font-semibold">{title}</h3>
        <button onClick={onClose} className="text-zinc-400 hover:text-zinc-200 text-lg leading-none">
          &times;
        </button>
      </div>
      <div className="px-5 py-4">{children}</div>
    </dialog>
  );
}
