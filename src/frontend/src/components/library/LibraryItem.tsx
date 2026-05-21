/**
 * LibraryItem — a single card in the library grid.
 *
 * Shows cover/preview, title, author, format, visibility badge,
 * and action buttons: local-download, send-to-ACW, send-to-folder, delete.
 */

import { useState } from 'react';
import type { LibraryItem as Item } from '../../services/libraryApi';
import { getApiBase } from '../../utils/basePath';
import { SendToFolderModal } from './SendToFolderModal';

interface LibraryItemProps {
  item: Item;
  onSendToAcw: (taskId: string) => Promise<string>;
  onSendToFolder: (taskId: string, folder: string) => Promise<string>;
  onDelete: (taskId: string) => Promise<void>;
  onShowToast?: (message: string, type: 'success' | 'error' | 'info') => void;
}

const STATUS_COLOR: Record<string, string> = {
  complete: 'text-green-600 dark:text-green-400',
  error: 'text-red-500',
  cancelled: 'opacity-50',
};

export function LibraryItem({
  item,
  onSendToAcw,
  onSendToFolder,
  onDelete,
  onShowToast,
}: LibraryItemProps) {
  const [busy, setBusy] = useState<'acw' | 'folder' | 'delete' | null>(null);
  const [showFolderModal, setShowFolderModal] = useState(false);

  const apiBase = getApiBase();

  const handleAction = async (
    kind: 'acw' | 'delete',
    action: () => Promise<string | void>,
    successMsg: string,
  ) => {
    setBusy(kind);
    try {
      await action();
      onShowToast?.(successMsg, 'success');
    } catch (err) {
      onShowToast?.(err instanceof Error ? err.message : 'Action failed', 'error');
    } finally {
      setBusy(null);
    }
  };

  const handleFolderConfirm = async (folder: string) => {
    const dest = await onSendToFolder(item.task_id, folder);
    onShowToast?.(`Sent to ${dest}`, 'success');
  };

  const localDownloadUrl = `${apiBase}/localdownload?id=${encodeURIComponent(item.task_id)}`;

  return (
    <>
      <div className="relative flex flex-col rounded-xl border border-(--border-muted) bg-(--bg-soft) overflow-hidden hover:border-(--border) transition-colors">
        {/* Cover / preview */}
        {item.preview ? (
          <img
            src={`${apiBase}/covers/${encodeURIComponent(item.task_id)}?url=${encodeURIComponent(btoa(item.preview))}`}
            alt={item.title}
            className="h-36 w-full object-cover bg-(--bg)"
            onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
          />
        ) : (
          <div className="h-36 w-full bg-(--bg) flex items-center justify-center opacity-20">
            <svg viewBox="0 0 24 24" className="h-10 w-10" fill="currentColor">
              <path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm-7 3a5 5 0 110 10A5 5 0 0112 6zm0 2a3 3 0 100 6 3 3 0 000-6z" />
            </svg>
          </div>
        )}

        {/* Visibility badge */}
        <span
          className={`absolute top-2 right-2 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
            item.visibility === 'private'
              ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
              : 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
          }`}
        >
          {item.visibility}
        </span>

        {/* Info */}
        <div className="flex-1 p-3">
          <p className="text-sm font-medium leading-snug line-clamp-2" title={item.title}>
            {item.title}
          </p>
          {item.author && (
            <p className="mt-0.5 text-xs opacity-60 line-clamp-1">{item.author}</p>
          )}
          <div className="mt-1.5 flex items-center gap-2 text-xs opacity-50">
            {item.format && <span>{item.format.toUpperCase()}</span>}
            {item.size && <span>· {item.size}</span>}
            <span className={`ml-auto ${STATUS_COLOR[item.final_status] ?? ''}`}>
              {item.final_status}
            </span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 border-t border-(--border-muted) p-2">
          {/* Local download */}
          {item.file_exists && (
            <a
              href={localDownloadUrl}
              title="Download"
              className="flex-1 flex items-center justify-center rounded-lg py-1.5 text-xs hover:bg-(--hover-surface) transition-colors gap-1"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
                <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
              </svg>
              Download
            </a>
          )}

          {/* Send to ACW */}
          {item.file_exists && (
            <button
              type="button"
              title="Send to Calibre Web"
              disabled={busy !== null}
              onClick={() =>
                void handleAction(
                  'acw',
                  () => onSendToAcw(item.task_id),
                  'Sent to Calibre Web',
                )
              }
              className="flex-1 flex items-center justify-center rounded-lg py-1.5 text-xs hover:bg-(--hover-surface) disabled:opacity-50 transition-colors gap-1"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path d="M3 3.5A1.5 1.5 0 014.5 2h6.879a1.5 1.5 0 011.06.44l4.122 4.12A1.5 1.5 0 0117 7.622V16.5a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 013 16.5v-13z" />
              </svg>
              {busy === 'acw' ? '…' : 'ACW'}
            </button>
          )}

          {/* Send to folder */}
          {item.file_exists && (
            <button
              type="button"
              title="Send to folder"
              disabled={busy !== null}
              onClick={() => setShowFolderModal(true)}
              className="flex-1 flex items-center justify-center rounded-lg py-1.5 text-xs hover:bg-(--hover-surface) disabled:opacity-50 transition-colors gap-1"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
                <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
              </svg>
              Folder
            </button>
          )}

          {/* Delete */}
          <button
            type="button"
            title="Delete"
            disabled={busy !== null}
            onClick={() =>
              void handleAction(
                'delete',
                async () => { await onDelete(item.task_id); },
                'Deleted',
              )
            }
            className="flex items-center justify-center rounded-lg p-1.5 text-xs hover:bg-red-50 hover:text-red-600 dark:hover:bg-red-900/20 disabled:opacity-50 transition-colors"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
      </div>

      {showFolderModal && (
        <SendToFolderModal
          title={item.title}
          onConfirm={handleFolderConfirm}
          onClose={() => setShowFolderModal(false)}
        />
      )}
    </>
  );
}
