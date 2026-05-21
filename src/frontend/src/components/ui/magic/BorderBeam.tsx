/**
 * BorderBeam — an animated beam that travels around the border of a container.
 *
 * The parent element MUST have `position: relative` and `overflow: hidden`.
 *
 * Adapted from magicui.design for Tailwind v4 (no "use client", local cn,
 * CSS variable classes use v4 `(--var)` syntax).
 */

import { motion } from 'motion/react';
import type { CSSProperties } from 'react';
import type { Transition } from 'motion/react';

import { cn } from './cn';

interface BorderBeamProps {
  size?: number;
  duration?: number;
  delay?: number;
  colorFrom?: string;
  colorTo?: string;
  transition?: Transition;
  className?: string;
  style?: CSSProperties;
  reverse?: boolean;
  initialOffset?: number;
  borderWidth?: number;
}

export function BorderBeam({
  className,
  size = 50,
  delay = 0,
  duration = 6,
  colorFrom = '#ffaa40',
  colorTo = '#9c40ff',
  transition,
  style,
  reverse = false,
  initialOffset = 0,
  borderWidth = 1,
}: BorderBeamProps) {
  return (
    <div
      className="pointer-events-none absolute inset-0 rounded-[inherit] border border-transparent [mask-composite:intersect] [mask-image:linear-gradient(transparent,transparent),linear-gradient(#000,#000)] [mask-clip:padding-box,border-box]"
      style={{ '--border-beam-width': `${borderWidth}px`, borderWidth: `var(--border-beam-width)` } as CSSProperties}
    >
      <motion.div
        className={cn('absolute aspect-square bg-linear-to-l', className)}
        style={
          {
            width: size,
            offsetPath: `rect(0 auto auto 0 round ${size}px)`,
            '--color-from': colorFrom,
            '--color-to': colorTo,
            background: `linear-gradient(to left, var(--color-from), var(--color-to), transparent)`,
            ...style,
          } as CSSProperties
        }
        initial={{ offsetDistance: `${initialOffset}%` }}
        animate={{
          offsetDistance: reverse
            ? [`${100 - initialOffset}%`, `${-initialOffset}%`]
            : [`${initialOffset}%`, `${100 + initialOffset}%`],
        }}
        transition={{
          repeat: Infinity,
          ease: 'linear',
          duration,
          delay: -delay,
          ...transition,
        }}
      />
    </div>
  );
}
