/**
 * LibraryOpenBook — 3D open-book modal with Framer Motion layout morphing.
 * Inline styles are used for all 3D transforms (CSS perspective / rotateY chains).
 */

import { useState } from 'react';
import { motion } from 'motion/react';
import type { LibraryItem } from '../../services/libraryApi';

interface Props {
  book: LibraryItem;
  onClose: () => void;
}

// Shared page dimensions
const PAGE_H = 'min(60vw, 500px)';
const PAGE_W = 'min(30vw, 250px)';

export function LibraryOpenBook({ book, onClose }: Props) {
  const [hovered, setHovered] = useState(false);

  // Book-wrap base / hover transforms
  const bookWrapStyle: React.CSSProperties = {
    position: 'relative',
    display: 'flex',
    flexDirection: 'row',
    transformStyle: 'preserve-3d',
    transform: hovered
      ? 'translate3d(0,5%,-264px) rotateX(13deg) rotateY(0) rotateZ(-3deg)'
      : 'translate3d(0,5%,-264px) rotateX(27deg) rotateY(0) rotateZ(-10deg)',
    transition: 'transform 650ms cubic-bezier(0.165, 0.84, 0.44, 1)',
  };

  // Shared page base styles
  const pageBase: React.CSSProperties = {
    width: PAGE_W,
    height: PAGE_H,
    position: 'absolute',
    top: 0,
    borderRadius: '2px',
    backfaceVisibility: 'hidden',
  };

  const coverBg = book.preview
    ? `url(${book.preview}) center/cover no-repeat`
    : 'linear-gradient(135deg, #2e1800 0%, #4a2c10 100%)';

  return (
    <motion.div
      layoutId={`book-${book.task_id}`}
      style={{
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        pointerEvents: 'auto',
        maxWidth: 900,
        width: '100%',
        padding: '2rem',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Close button */}
      <button
        type="button"
        onClick={onClose}
        style={{
          position: 'absolute',
          top: '0.5rem',
          right: '0.5rem',
          zIndex: 10,
          background: 'rgba(0,0,0,0.5)',
          border: '1px solid rgba(255,255,255,0.2)',
          borderRadius: '50%',
          width: '2rem',
          height: '2rem',
          cursor: 'pointer',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '1rem',
          lineHeight: 1,
        }}
        aria-label="Close"
      >
        ×
      </button>

      {/* Scene — perspective container */}
      <div
        style={{
          perspective: '2000px',
          perspectiveOrigin: '50% 50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '100%',
          height: `calc(${PAGE_H} + 4rem)`,
        }}
      >
        {/* Book-wrap */}
        <div style={bookWrapStyle}>

          {/* ── Left side ─────────────────────────────────────── */}
          <div
            style={{
              position: 'relative',
              width: PAGE_W,
              height: PAGE_H,
              transformStyle: 'preserve-3d',
              transform: 'rotateY(20deg)',
              transformOrigin: '100% 50%',
            }}
          >
            {/* Book cover left */}
            <div
              style={{
                ...pageBase,
                background: '#2e1800',
                boxShadow:
                  'inset 4px -4px 4px 1px #635648, inset 7px -7px 4px 0 #221b14',
              }}
            />

            {/* Page stack shadows — left */}
            <div
              style={{
                ...pageBase,
                background: '#fff',
                boxShadow:
                  'inset 0 0 26px 2px #d8cccc, -1px 1px 13px 0 rgba(34,27,20,0.81)',
                transform: 'translate3d(0,0,5px)',
              }}
            />
            <div
              style={{
                ...pageBase,
                background: '#fff',
                boxShadow:
                  'inset 0 0 26px 2px #d8cccc, -1px 1px 13px 0 rgba(34,27,20,0.81)',
                transform: 'translate3d(2px,0,10px)',
              }}
            />
            <div
              style={{
                ...pageBase,
                background: '#fff',
                boxShadow:
                  'inset 0 0 26px 2px #d8cccc, -1px 1px 13px 0 rgba(34,27,20,0.81)',
                transform: 'translate3d(4px,0,20px)',
              }}
            />
            <div
              style={{
                ...pageBase,
                background: '#fff',
                boxShadow:
                  'inset 0 0 26px 2px #d8cccc, -1px 1px 13px 0 rgba(34,27,20,0.81)',
                transform: 'translate3d(6px,0,30px)',
              }}
            />

            {/* Layer-text — metadata page */}
            <div
              style={{
                ...pageBase,
                transform: 'translate3d(0,0,32px)',
                transformStyle: 'preserve-3d',
                overflow: 'hidden',
              }}
            >
              {/* Page-left-2: slightly rotated, hover effect */}
              <div
                style={{
                  width: '100%',
                  height: '100%',
                  background: '#fff',
                  boxShadow:
                    'inset 0 0 7px 4px hsla(0,13%,82%,0.43), -1px 1px 13px 0 rgba(34,27,20,0.49)',
                  transform: hovered ? 'rotateY(7deg)' : 'rotateY(17deg)',
                  transformOrigin: '100% 50%',
                  transition: 'transform 650ms cubic-bezier(0.165, 0.84, 0.44, 1)',
                  overflow: 'hidden',
                  borderRadius: '2px',
                }}
              >
                {/* Metadata content */}
                <div
                  style={{
                    fontFamily: 'Georgia, serif',
                    padding: '1.5rem',
                    overflowY: 'auto',
                    height: '100%',
                    color: '#221b14',
                    boxSizing: 'border-box',
                  }}
                >
                  <h2
                    style={{
                      fontFamily: 'Palatino Linotype, Palatino, serif',
                      fontStyle: 'italic',
                      fontSize: '1rem',
                      margin: '0 0 1rem',
                      lineHeight: 1.3,
                      color: '#2e1800',
                    }}
                  >
                    {book.title}
                  </h2>
                  {book.author && (
                    <p style={{ margin: '0.35rem 0', fontSize: '0.72rem' }}>
                      <strong>Author:</strong> {book.author}
                    </p>
                  )}
                  {book.format && (
                    <p style={{ margin: '0.35rem 0', fontSize: '0.72rem' }}>
                      <strong>Format:</strong> {book.format.toUpperCase()}
                    </p>
                  )}
                  {book.content_type && (
                    <p style={{ margin: '0.35rem 0', fontSize: '0.72rem' }}>
                      <strong>Type:</strong> {book.content_type}
                    </p>
                  )}
                  {book.size && (
                    <p style={{ margin: '0.35rem 0', fontSize: '0.72rem' }}>
                      <strong>Size:</strong> {book.size}
                    </p>
                  )}
                  <p style={{ margin: '0.35rem 0', fontSize: '0.72rem' }}>
                    <strong>Source:</strong>{' '}
                    {book.source_display_name ?? book.source}
                  </p>
                  {book.terminal_at && (
                    <p style={{ margin: '0.35rem 0', fontSize: '0.72rem' }}>
                      <strong>Downloaded:</strong>{' '}
                      {new Date(book.terminal_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* ── Spine / Center ────────────────────────────────── */}
          <div
            style={{
              width: '2rem',
              height: PAGE_H,
              flexShrink: 0,
              background:
                'linear-gradient(90deg, #635648, #2e1800 21%, #635648 30%, #2e1800 48%, #635648 68%, #2e1800 79%, #635648)',
              position: 'relative',
              zIndex: 1,
            }}
          >
            {/* Top radial highlight */}
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: '30%',
                background:
                  'radial-gradient(ellipse at 50% 0%, rgba(255,255,255,0.15) 0%, transparent 70%)',
              }}
            />
            {/* Bottom radial shadow */}
            <div
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                height: '30%',
                background:
                  'radial-gradient(ellipse at 50% 100%, rgba(0,0,0,0.4) 0%, transparent 70%)',
              }}
            />
          </div>

          {/* ── Right side ────────────────────────────────────── */}
          <div
            style={{
              position: 'relative',
              width: PAGE_W,
              height: PAGE_H,
              transformStyle: 'preserve-3d',
              transform: 'rotateY(-1deg)',
              transformOrigin: '0% 50%',
            }}
          >
            {/* Book cover right */}
            <div
              style={{
                ...pageBase,
                background: '#2e1800',
                boxShadow:
                  'inset -4px -4px 4px 1px #635648, inset -7px -7px 4px 0 #221b14',
              }}
            />

            {/* Page stack shadows — right */}
            <div
              style={{
                ...pageBase,
                background: '#fff',
                boxShadow:
                  'inset 0 0 26px 2px #d8cccc, 1px 1px 13px 0 rgba(34,27,20,0.81)',
                transform: 'translate3d(0,0,5px)',
              }}
            />
            <div
              style={{
                ...pageBase,
                background: '#fff',
                boxShadow:
                  'inset 0 0 26px 2px #d8cccc, 1px 1px 13px 0 rgba(34,27,20,0.81)',
                transform: 'translate3d(-5px,0,10px)',
              }}
            />
            <div
              style={{
                ...pageBase,
                background: '#fff',
                boxShadow:
                  'inset 0 0 26px 2px #d8cccc, 1px 1px 13px 0 rgba(34,27,20,0.81)',
                transform: 'translate3d(-10px,0,20px)',
              }}
            />
            <div
              style={{
                ...pageBase,
                background: '#fff',
                boxShadow:
                  'inset 0 0 26px 2px #d8cccc, 1px 1px 13px 0 rgba(34,27,20,0.81)',
                transform: 'translate3d(-15px,0,30px)',
              }}
            />

            {/* Layer-text right — description / cover fallback page */}
            <div
              style={{
                ...pageBase,
                transform: 'translate3d(-37px,0,32px)',
                transformStyle: 'preserve-3d',
                overflow: 'hidden',
              }}
            >
              {/* Page-right-2 */}
              <div
                style={{
                  width: '100%',
                  height: '100%',
                  background: '#fff',
                  boxShadow:
                    'inset 0 0 7px 4px hsla(0,13%,82%,0.43), 1px 1px 13px 0 rgba(34,27,20,0.49)',
                  transform: hovered ? 'rotateY(-17deg)' : 'rotateY(-3deg)',
                  transformOrigin: '0% 50%',
                  transition: 'transform 650ms cubic-bezier(0.165, 0.84, 0.44, 1)',
                  overflow: 'hidden',
                  borderRadius: '2px',
                }}
              >
                {book.description ? (
                  <div style={{ fontFamily: 'Georgia, serif', padding: '1.5rem', overflowY: 'auto', height: '100%', color: '#221b14', boxSizing: 'border-box' }}>
                    <h3 style={{ fontFamily: 'Palatino Linotype, Palatino, serif', fontStyle: 'italic', fontSize: '0.8rem', margin: '0 0 0.75rem', opacity: 0.6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>About this book</h3>
                    <p style={{ fontSize: '0.7rem', lineHeight: 1.6, margin: 0 }}>{book.description}</p>
                  </div>
                ) : (
                  <div style={{ width: '100%', height: '100%', background: coverBg, borderRadius: '2px' }}>
                    {!book.preview && (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'rgba(255,255,255,0.3)', fontSize: '3rem' }}>📚</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
