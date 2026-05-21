/**
 * SendToFolderModal — prompts for an absolute destination folder path,
 * then calls onConfirm with the entered path.
 */

import { useCallback, useRef, useState } from 'react';

interface SendToFolderModalProps {
  title: string;
  onConfirm: (folder: string) => Promise<void>;
  onClose: () => void;
}

export function SendToFolderModal({ title, onConfirm, onClose }: SendToFolderModalProps) {
  const [folder, setFolder] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = folder.trim();
      if (!trimmed) {
        setError('Please enter a folder path');
        inputRef.current?.focus();
        return;
      }
      if (!trimmed.startsWith('/')) {
        setError('Path must be absolute (start with /)');
        return;
      }
      setIsSubmitting(true);
      setError(null);
      try {
        await onConfirm(trimmed);
        onClose();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send');
      } finally {
        setIsSubmitting(false);
      }
    },
    [folder, onConfirm, onClose],
  );

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        className="w-full max-w-md rounded-xl border border-(--border-muted) bg-(--bg) p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="mb-1 text-base font-semibold">Send to folder</h2>
        <p className="mb-4 text-sm opacity-60 truncate">{title}</p>

        <form onSubmit={(e) => { void handleSubmit(e); }}>
          <input
            ref={inputRef}
            type="text"
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            placeholder="/path/to/destination"
            autoFocus
            className="w-full rounded-lg border border-(--border-muted) bg-(--bg-soft) px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-(--accent)"
          />
          {error && <p className="mt-2 text-xs text-red-500">{error}</p>}

          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-(--border-muted) px-4 py-2 text-sm hover:bg-(--hover-surface) transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-lg bg-(--accent) px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {isSubmitting ? 'Copying…' : 'Send'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
