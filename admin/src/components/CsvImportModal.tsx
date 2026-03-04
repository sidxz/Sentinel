import { useState } from "react";
import { Modal } from "./Modal";
import { csvPreview, csvExecute } from "../api/client";
import type { CsvImportPreview, CsvImportResult } from "../types/api";

interface Props {
  open: boolean;
  onClose: () => void;
  onComplete: () => void;
}

export function CsvImportModal({ open, onClose, onComplete }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<CsvImportPreview | null>(null);
  const [result, setResult] = useState<CsvImportResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await csvPreview(file);
      setPreview(data);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const data = await csvExecute(file);
      setResult(data);
      onComplete();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal open={open} onClose={handleClose} title="Import CSV">
      <div className="space-y-4">
        {!result ? (
          <>
            <div>
              <label className="text-xs text-zinc-500">
                CSV with columns: email, name, workspace_slug, role
              </label>
              <input
                type="file"
                accept=".csv"
                onChange={(e) => {
                  setFile(e.target.files?.[0] ?? null);
                  setPreview(null);
                }}
                className="mt-1 block w-full text-sm text-zinc-400 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-medium file:bg-zinc-800 file:text-zinc-300 hover:file:bg-zinc-700"
              />
            </div>

            {error && (
              <div className="text-xs text-red-400 bg-red-500/5 border border-red-500/20 rounded px-3 py-2">
                {error}
              </div>
            )}

            {preview && (
              <div className="space-y-2">
                <div className="flex gap-3 text-xs">
                  <span className="text-emerald-400">{preview.valid_count} valid</span>
                  {preview.error_count > 0 && (
                    <span className="text-red-400">{preview.error_count} errors</span>
                  )}
                </div>
                <div className="max-h-48 overflow-auto rounded border border-zinc-800">
                  <table className="w-full text-xs">
                    <thead className="bg-zinc-800/50">
                      <tr>
                        <th className="px-2 py-1 text-left text-zinc-500">Email</th>
                        <th className="px-2 py-1 text-left text-zinc-500">Name</th>
                        <th className="px-2 py-1 text-left text-zinc-500">Workspace</th>
                        <th className="px-2 py-1 text-left text-zinc-500">Role</th>
                        <th className="px-2 py-1 text-left text-zinc-500">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/50">
                      {preview.rows.map((row, i) => (
                        <tr key={i} className={row.error ? "bg-red-500/5" : ""}>
                          <td className="px-2 py-1 text-zinc-300">{row.email}</td>
                          <td className="px-2 py-1 text-zinc-400">{row.name}</td>
                          <td className="px-2 py-1 text-zinc-400">{row.workspace_slug}</td>
                          <td className="px-2 py-1 text-zinc-400">{row.role}</td>
                          <td className="px-2 py-1">
                            {row.error ? (
                              <span className="text-red-400">{row.error}</span>
                            ) : (
                              <span className="text-emerald-400">OK</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={handleClose} className="px-3 py-1.5 rounded text-xs text-zinc-400 hover:text-zinc-200">
                Cancel
              </button>
              {!preview ? (
                <button
                  onClick={handlePreview}
                  disabled={!file || loading}
                  className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white disabled:opacity-50"
                >
                  {loading ? "Parsing..." : "Preview"}
                </button>
              ) : (
                <button
                  onClick={handleExecute}
                  disabled={loading || preview.valid_count === 0}
                  className="px-3 py-1.5 rounded text-xs font-medium bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 ring-1 ring-emerald-500/20 disabled:opacity-50"
                >
                  {loading ? "Importing..." : `Import ${preview.valid_count} rows`}
                </button>
              )}
            </div>
          </>
        ) : (
          <div className="space-y-3">
            <div className="text-sm text-zinc-300">Import complete</div>
            <div className="flex gap-4 text-xs">
              <span className="text-emerald-400">{result.users_created} users created</span>
              <span className="text-blue-400">{result.memberships_added} memberships added</span>
            </div>
            {result.errors.length > 0 && (
              <div className="space-y-1">
                {result.errors.map((e, i) => (
                  <div key={i} className="text-xs text-red-400">{e}</div>
                ))}
              </div>
            )}
            <div className="flex justify-end pt-2">
              <button
                onClick={handleClose}
                className="px-3 py-1.5 rounded text-xs font-medium bg-zinc-100 text-zinc-900 hover:bg-white"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
