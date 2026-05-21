/**
 * LibraryFilters — search bar + visibility + status filter bar for the Library screen.
 */

import { useCallback, useRef } from 'react';
import type { LibraryFilters as Filters } from '../../services/libraryApi';

interface LibraryFiltersProps {
  filters: Filters;
  onFiltersChange: (partial: Partial<Filters>) => void;
}

export function LibraryFilters({ filters, onFiltersChange }: LibraryFiltersProps) {
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearch = useCallback(
    (value: string) => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => onFiltersChange({ q: value || undefined }), 300);
    },
    [onFiltersChange],
  );

  return (
    <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-(--border-muted)">
      {/* Search */}
      <input
        type="search"
        placeholder="Search title or author…"
        defaultValue={filters.q ?? ''}
        onChange={(e) => handleSearch(e.target.value)}
        className="flex-1 min-w-[180px] max-w-xs rounded-lg border border-(--border-muted) bg-(--bg-soft) px-3 py-1.5 text-sm placeholder:opacity-50 focus:outline-none focus:ring-2 focus:ring-(--accent)"
      />

      {/* Visibility */}
      <select
        value={filters.visibility ?? 'all'}
        onChange={(e) => onFiltersChange({ visibility: e.target.value as Filters['visibility'] })}
        className="rounded-lg border border-(--border-muted) bg-(--bg-soft) px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-(--accent)"
      >
        <option value="all">All</option>
        <option value="public">Public</option>
        <option value="private">Private</option>
      </select>

      {/* Status */}
      <select
        value={filters.final_status ?? ''}
        onChange={(e) =>
          onFiltersChange({
            final_status: (e.target.value as Filters['final_status']) || undefined,
          })
        }
        className="rounded-lg border border-(--border-muted) bg-(--bg-soft) px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-(--accent)"
      >
        <option value="">Any status</option>
        <option value="complete">Complete</option>
        <option value="error">Error</option>
        <option value="cancelled">Cancelled</option>
      </select>
    </div>
  );
}
