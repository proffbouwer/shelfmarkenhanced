/**
 * LibraryShelfView — orchestrates the animated book shelf and open-book modal.
 */

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';

import type { LibraryItem } from '../../services/libraryApi';
import { LibraryBookCard } from './LibraryBookCard';
import { LibraryOpenBook } from './LibraryOpenBook';
import './library-shelf.css';

interface Props {
  items: LibraryItem[];
  isLoading: boolean;
  onSendToAcw: (taskId: string) => Promise<string>;
  onSendToFolder: (taskId: string, folder: string) => Promise<string>;
  onDelete: (taskId: string) => Promise<void>;
  onShowToast?: (message: string, type: 'success' | 'error' | 'info') => void;
}

export function LibraryShelfView({
  items,
  isLoading: _isLoading,
  onSendToAcw: _onSendToAcw,
  onSendToFolder: _onSendToFolder,
  onDelete: _onDelete,
  onShowToast: _onShowToast,
}: Props) {
  const [selectedBook, setSelectedBook] = useState<LibraryItem | null>(null);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedBook(null);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  if (items.length === 0) {
    return (
      <div className="lib-shelf-wrap" style={{ minHeight: '12rem', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: 0.5 }}>
        <div style={{ textAlign: 'center' }}>
          <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: '3rem', height: '3rem', display: 'block', margin: '0 auto 0.5rem' }}>
            <path d="M11.25 4.533A9.707 9.707 0 006 3a9.735 9.735 0 00-3.25.555.75.75 0 00-.5.707v14.25a.75.75 0 001 .707A8.237 8.237 0 016 18.75c1.995 0 3.823.707 5.25 1.886V4.533zM12.75 20.636A8.214 8.214 0 0118 18.75c.966 0 1.89.166 2.75.47a.75.75 0 001-.708V4.262a.75.75 0 00-.5-.707A9.735 9.735 0 0018 3a9.707 9.707 0 00-5.25 1.533v16.103z" />
          </svg>
          <span style={{ fontSize: '0.875rem' }}>No downloads found</span>
        </div>
      </div>
    );
  }

  return (
    <div className="lib-shelf-wrap">
      <section className="lib-section">
        <h2 className="lib-section-header">Library</h2>
        {items.map((item, i) => (
          <LibraryBookCard
            key={item.task_id}
            item={item}
            index={i}
            onOpen={setSelectedBook}
          />
        ))}
      </section>

      <AnimatePresence>
        {selectedBook && (
          <>
            {/* Blurred backdrop */}
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSelectedBook(null)}
              style={{
                position: 'fixed',
                inset: 0,
                zIndex: 45,
                background: 'rgba(0,0,0,0.75)',
                backdropFilter: 'blur(4px)',
              }}
            />

            {/* Open book modal */}
            <div
              style={{
                position: 'fixed',
                inset: 0,
                zIndex: 50,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                pointerEvents: 'none',
              }}
            >
              <LibraryOpenBook
                book={selectedBook}
                onClose={() => setSelectedBook(null)}
              />
            </div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
