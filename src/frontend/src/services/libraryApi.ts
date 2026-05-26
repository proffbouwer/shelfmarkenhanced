/**
 * Library API — completed downloads browser.
 */

import { getApiBase } from '../utils/basePath';

const API_BASE = getApiBase();
const LIBRARY_URL = `${API_BASE}/library`;

export type LibraryVisibility = 'public' | 'private';

export interface LibraryItem {
  task_id: string;
  title: string;
  author: string | null;
  format: string | null;
  size: string | null;
  preview: string | null;
  description?: string | null;
  content_type: string | null;
  source: string;
  source_display_name: string | null;
  visibility: LibraryVisibility;
  final_status: 'complete' | 'error' | 'cancelled';
  download_path: string | null;
  file_exists: boolean;
  user_id: number | null;
  username: string | null;
  queued_at: string | null;
  terminal_at: string | null;
  request_id: number | null;
}

export interface LibraryListResponse {
  items: LibraryItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface LibraryFilters {
  page?: number;
  page_size?: number;
  visibility?: 'all' | LibraryVisibility;
  q?: string;
  final_status?: 'complete' | 'error' | 'cancelled';
}

export const fetchLibrary = async (filters: LibraryFilters = {}): Promise<LibraryListResponse> => {
  const params = new URLSearchParams();
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));
  if (filters.visibility) params.set('visibility', filters.visibility);
  if (filters.q) params.set('q', filters.q);
  if (filters.final_status) params.set('final_status', filters.final_status);

  const url = params.toString() ? `${LIBRARY_URL}?${params.toString()}` : LIBRARY_URL;
  const res = await fetch(url, { credentials: 'include' });
  if (!res.ok) throw new Error(`Library fetch failed: ${res.statusText}`);
  return res.json() as Promise<LibraryListResponse>;
};

export const sendToAcw = async (taskId: string): Promise<{ status: string; dest: string }> => {
  const res = await fetch(`${LIBRARY_URL}/${encodeURIComponent(taskId)}/send-to-acw`, {
    method: 'POST',
    credentials: 'include',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(body.error ?? `send-to-acw failed: ${res.statusText}`);
  }
  return res.json() as Promise<{ status: string; dest: string }>;
};

export const sendToFolder = async (
  taskId: string,
  folder: string,
): Promise<{ status: string; dest: string }> => {
  const res = await fetch(`${LIBRARY_URL}/${encodeURIComponent(taskId)}/send-to-folder`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ folder }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(body.error ?? `send-to-folder failed: ${res.statusText}`);
  }
  return res.json() as Promise<{ status: string; dest: string }>;
};

export const deleteLibraryItem = async (
  taskId: string,
): Promise<{ status: string; deleted_file: boolean }> => {
  const res = await fetch(`${LIBRARY_URL}/${encodeURIComponent(taskId)}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({})) as { error?: string };
    throw new Error(body.error ?? `delete failed: ${res.statusText}`);
  }
  return res.json() as Promise<{ status: string; deleted_file: boolean }>;
};
