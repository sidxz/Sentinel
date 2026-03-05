import { apiFetch } from "./client";

export interface Note {
  id: string;
  title: string;
  content: string;
  workspace_id: string;
  owner_id: string;
  owner_name: string;
  created_at: string;
  updated_at: string;
}

export interface UserInfo {
  user_id: string;
  email: string;
  name: string;
  workspace_id: string;
  workspace_slug: string;
  workspace_role: string;
  groups: string[];
}

export function fetchMe(): Promise<UserInfo> {
  return apiFetch("/me");
}

export function fetchMyActions(): Promise<{ actions: string[] }> {
  return apiFetch("/me/actions");
}

export function fetchNotes(): Promise<Note[]> {
  return apiFetch("/notes");
}

export function fetchNote(id: string): Promise<Note> {
  return apiFetch(`/notes/${id}`);
}

export function createNote(title: string, content: string): Promise<Note> {
  return apiFetch("/notes", {
    method: "POST",
    body: JSON.stringify({ title, content }),
  });
}

export function updateNote(
  id: string,
  data: { title?: string; content?: string }
): Promise<Note> {
  return apiFetch(`/notes/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export function deleteNote(id: string): Promise<{ ok: boolean }> {
  return apiFetch(`/notes/${id}`, { method: "DELETE" });
}

export function shareNote(
  noteId: string,
  userId: string,
  permission: string
): Promise<{ ok: boolean }> {
  return apiFetch(`/notes/${noteId}/share`, {
    method: "POST",
    body: JSON.stringify({ user_id: userId, permission }),
  });
}

export function exportNotes(): Promise<{
  format: string;
  count: number;
  notes: Note[];
}> {
  return apiFetch("/notes/export");
}
