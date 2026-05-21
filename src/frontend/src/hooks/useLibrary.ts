/**
 * useLibrary — data-fetching hook for the Library screen.
 *
 * Manages pagination, filtering, and individual item actions
 * (send-to-ACW, send-to-folder, delete).
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  deleteLibraryItem,
  fetchLibrary,
  sendToAcw,
  sendToFolder,
} from '../services/libraryApi';
import type { LibraryFilters, LibraryItem } from '../services/libraryApi';

interface UseLibraryState {
  items: LibraryItem[];
  total: number;
  page: number;
  pageSize: number;
  isLoading: boolean;
  error: string | null;
}

interface UseLibraryActions {
  refresh: () => void;
  setPage: (page: number) => void;
  setFilters: (filters: Partial<LibraryFilters>) => void;
  handleSendToAcw: (taskId: string) => Promise<string>;
  handleSendToFolder: (taskId: string, folder: string) => Promise<string>;
  handleDelete: (taskId: string) => Promise<void>;
}

const DEFAULT_PAGE_SIZE = 50;

export function useLibrary(
  initialFilters: LibraryFilters = {},
): UseLibraryState & UseLibraryActions {
  const [filters, setFiltersState] = useState<LibraryFilters>({
    page: 1,
    page_size: DEFAULT_PAGE_SIZE,
    visibility: 'all',
    ...initialFilters,
  });

  const [state, setState] = useState<Omit<UseLibraryState, 'page' | 'pageSize'>>({
    items: [],
    total: 0,
    isLoading: false,
    error: null,
  });

  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async (f: LibraryFilters) => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();

    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const data = await fetchLibrary(f);
      setState({ items: data.items, total: data.total, isLoading: false, error: null });
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Failed to load library',
      }));
    }
  }, []);

  useEffect(() => {
    void load(filters);
    return () => abortRef.current?.abort();
  }, [filters, load]);

  const refresh = useCallback(() => void load(filters), [filters, load]);

  const setPage = useCallback((page: number) => {
    setFiltersState((prev) => ({ ...prev, page }));
  }, []);

  const setFilters = useCallback((partial: Partial<LibraryFilters>) => {
    setFiltersState((prev) => ({ ...prev, ...partial, page: 1 }));
  }, []);

  const handleSendToAcw = useCallback(async (taskId: string) => {
    const result = await sendToAcw(taskId);
    return result.dest;
  }, []);

  const handleSendToFolder = useCallback(async (taskId: string, folder: string) => {
    const result = await sendToFolder(taskId, folder);
    return result.dest;
  }, []);

  const handleDelete = useCallback(
    async (taskId: string) => {
      await deleteLibraryItem(taskId);
      setState((prev) => ({
        ...prev,
        items: prev.items.filter((i) => i.task_id !== taskId),
        total: Math.max(0, prev.total - 1),
      }));
    },
    [],
  );

  return {
    items: state.items,
    total: state.total,
    page: filters.page ?? 1,
    pageSize: filters.page_size ?? DEFAULT_PAGE_SIZE,
    isLoading: state.isLoading,
    error: state.error,
    refresh,
    setPage,
    setFilters,
    handleSendToAcw,
    handleSendToFolder,
    handleDelete,
  };
}
