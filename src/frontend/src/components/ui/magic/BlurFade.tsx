/**
 * BlurFade — animated entrance that blurs and slides content into view.
 * Wrap any content to apply a smooth blur-fade reveal on mount or scroll-into-view.
 *
 * Adapted from magicui.design for Tailwind v4 (no "use client", local cn).
 */

import { AnimatePresence, motion, useInView } from 'motion/react';
import type { MotionProps, UseInViewOptions, Variants } from 'motion/react';
import { useRef } from 'react';

type MarginType = UseInViewOptions['margin'];

interface BlurFadeProps extends MotionProps {
  children: React.ReactNode;
  className?: string;
  variant?: {
    hidden: { y: number };
    visible: { y: number };
  };
  duration?: number;
  delay?: number;
  offset?: number;
  direction?: 'up' | 'down' | 'left' | 'right';
  inView?: boolean;
  inViewMargin?: MarginType;
  blur?: string;
}

export function BlurFade({
  children,
  className,
  variant,
  duration = 0.4,
  delay = 0,
  offset = 6,
  direction = 'down',
  inView = false,
  inViewMargin = '-50px',
  blur = '6px',
  ...props
}: BlurFadeProps) {
  const ref = useRef(null);
  const inViewResult = useInView(ref, { once: true, margin: inViewMargin });
  const isInView = !inView || inViewResult;

  const defaultVariants: Variants = {
    hidden: {
      [direction === 'left' || direction === 'right' ? 'x' : 'y']:
        direction === 'right' || direction === 'down' ? -offset : offset,
      opacity: 0,
      filter: `blur(${blur})`,
    },
    visible: {
      [direction === 'left' || direction === 'right' ? 'x' : 'y']: 0,
      opacity: 1,
      filter: 'blur(0px)',
    },
  };

  const combinedVariants = variant ?? defaultVariants;

  const hiddenFilter =
    typeof combinedVariants.hidden !== 'function'
      ? (combinedVariants.hidden as Record<string, unknown>).filter
      : undefined;
  const visibleFilter =
    typeof combinedVariants.visible !== 'function'
      ? (combinedVariants.visible as Record<string, unknown>).filter
      : undefined;
  const shouldTransitionFilter =
    hiddenFilter != null && visibleFilter != null && hiddenFilter !== visibleFilter;

  return (
    <AnimatePresence>
      <motion.div
        ref={ref}
        initial="hidden"
        animate={isInView ? 'visible' : 'hidden'}
        exit="hidden"
        variants={combinedVariants}
        transition={{
          delay: 0.04 + delay,
          duration,
          ease: 'easeOut',
          ...(shouldTransitionFilter ? { filter: { duration } } : {}),
        }}
        className={className}
        {...props}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
