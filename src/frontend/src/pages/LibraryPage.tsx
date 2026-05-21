/**
 * LibraryPage — full-route screen at /library showing all completed downloads.
 *
 * Features:
 * - Paginated grid of download cards with cover image, title, author, format
 * - Visibility badges (public / private)
 * - Filter by visibility, status, free-text search
 * - Per-item actions: local download, send-to-ACW, send-to-folder, delete
 */

import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { LibraryGrid } from '../components/library/LibraryGrid';
import { LibraryFilters } from '../components/library/LibraryFilters';
import { useLibrary } from '../hooks/useLibrary';

interface LibraryPageProps {
  onShowToast?: (message: string, type: 'success' | 'error' | 'info') => void;
}

export function LibraryPage({ onShowToast }: LibraryPageProps) {
  const navigate = useNavigate();

  const {
    items,
    total,
    page,
    pageSize,
    isLoading,
    error,
    refresh,
    setPage,
    setFilters,
    handleSendToAcw,
    handleSendToFolder,
    handleDelete,
  } = useLibrary({ final_status: 'complete', visibility: 'all' });

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleClose = useCallback(() => navigate('/'), [navigate]);

  // ── Error state ────────────────────────────────────────────────────────────
  if (error) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4" style={{ background: 'var(--bg)' }}>
        <p className="text-sm text-red-500">{error}</p>
        <button type="button" onClick={handleClose} className="rounded-lg border border-(--border-muted) bg-(--bg-soft) px-4 py-2 text-sm hover:bg-(--hover-surface)">
          Go back
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-(--border-muted) px-4 py-3">
        <div className="flex items-center gap-3">
          <button type="button" onClick={handleClose} className="rounded-lg p-1.5 hover:bg-(--hover-surface) transition-colors" title="Close">
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-5 w-5">
              <path fillRule="evenodd" d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z" clipRule="evenodd" />
            </svg>
          </button>
          <h1 className="text-base font-semibold">Library</h1>
          {!isLoading && (
            <span className="rounded-full bg-(--bg-soft) px-2 py-0.5 text-xs opacity-60">
              {total} {total === 1 ? 'item' : 'items'}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={refresh}
          disabled={isLoading}
          className="rounded-lg p-1.5 hover:bg-(--hover-surface) transition-colors disabled:opacity-40"
          title="Refresh"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className={`h-5 w-5 ${isLoading ? 'animate-spin' : ''}`}>
            <path fillRule="evenodd" d="M15.312 11.424a5.5 5.5 0 01-9.201 2.466l-.312-.311h2.433a.75.75 0 000-1.5H3.989a.75.75 0 00-.75.75v4.242a.75.75 0 001.5 0v-2.43l.31.31a7 7 0 0011.712-3.138.75.75 0 00-1.449-.389zm1.23-3.723a.75.75 0 00.219-.53V2.929a.75.75 0 00-1.5 0V5.36l-.31-.31A7 7 0 003.239 8.188a.75.75 0 101.448.389A5.5 5.5 0 0113.89 6.11l.311.31h-2.432a.75.75 0 000 1.5h4.243a.75.75 0 00.53-.219z" clipRule="evenodd" />
          </svg>
        </button>
      </div>

      {/* Filters */}
      <LibraryFilters
        filters={{ visibility: 'all' }}
        onFiltersChange={setFilters}
      />

      {/* Loading state */}
      {isLoading && items.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <svg className="h-6 w-6 animate-spin opacity-40" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          <LibraryGrid
            items={items}
            onSendToAcw={handleSendToAcw}
            onSendToFolder={handleSendToFolder}
            onDelete={handleDelete}
            onShowToast={onShowToast}
          />
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 border-t border-(--border-muted) px-4 py-3">
          <button
            type="button"
            onClick={() => setPage(page - 1)}
            disabled={page <= 1 || isLoading}
            className="rounded-lg border border-(--border-muted) px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-(--hover-surface) transition-colors"
          >
            Previous
          </button>
          <span className="text-sm opacity-60">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage(page + 1)}
            disabled={page >= totalPages || isLoading}
            className="rounded-lg border border-(--border-muted) px-3 py-1.5 text-sm disabled:opacity-40 hover:bg-(--hover-surface) transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
