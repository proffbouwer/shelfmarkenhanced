/**
 * LibraryBookCard — animated book card for the shelf view.
 * Uses Framer Motion for entry animation and layout morphing.
 */

import { motion } from 'motion/react';
import type { LibraryItem } from '../../services/libraryApi';

// 20+ earthy/muted hex colors for deterministic card tinting
const CARD_COLORS = [
  '#b47460', '#8b6f5e', '#7a9e7e', '#6b8fa3', '#a07850',
  '#9e7a6b', '#6e8c6e', '#7e6b8c', '#a08070', '#6e8070',
  '#b08060', '#7a6e5a', '#8e9e7e', '#6a7e8e', '#9e8060',
  '#8e6e7e', '#6e9e8e', '#7e8e6e', '#9e6e60', '#7a8e9e',
  '#b0906e', '#6e7e6e', '#8e7060', '#9e8e6e', '#6e6e8e',
];

function colorFromId(id: string): string {
  let hash = 0;
  for (let i = 0; i < id.length; i++) {
    hash = (hash * 31 + id.charCodeAt(i)) >>> 0;
  }
  return CARD_COLORS[hash % CARD_COLORS.length];
}

interface Props {
  item: LibraryItem;
  onOpen: (item: LibraryItem) => void;
  index: number;
}

export function LibraryBookCard({ item, onOpen, index }: Props) {
  const color = colorFromId(item.task_id);

  return (
    <motion.article
      layoutId={`book-${item.task_id}`}
      className="lib-card"
      style={{ '--avarage-color': color } as React.CSSProperties}
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04, duration: 0.35 }}
      whileTap={{ scale: 0.97 }}
      onClick={() => onOpen(item)}
    >
      <figure>
        {item.preview ? (
          <img src={item.preview} alt={item.title} loading="lazy" />
        ) : (
          <div className="lib-card-placeholder">
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              style={{ width: '2rem', height: '2rem', opacity: 0.3 }}
            >
              <path d="M11.25 4.533A9.707 9.707 0 006 3a9.735 9.735 0 00-3.25.555.75.75 0 00-.5.707v14.25a.75.75 0 001 .707A8.237 8.237 0 016 18.75c1.995 0 3.823.707 5.25 1.886V4.533zM12.75 20.636A8.214 8.214 0 0118 18.75c.966 0 1.89.166 2.75.47a.75.75 0 001-.708V4.262a.75.75 0 00-.5-.707A9.735 9.735 0 0018 3a9.707 9.707 0 00-5.25 1.533v16.103z" />
            </svg>
          </div>
        )}
        <figcaption>{item.title}</figcaption>
      </figure>
      {item.author && (
        <div className="lib-card-author">{item.author}</div>
      )}
    </motion.article>
  );
}
