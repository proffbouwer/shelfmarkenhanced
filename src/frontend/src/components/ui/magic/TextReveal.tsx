/**
 * TextReveal — scroll-driven word-by-word text reveal animation.
 *
 * Wrap a string of text; each word fades in as the user scrolls through
 * the component's sticky scroll region (height: 200vh).
 *
 * Adapted from magicui.design for Tailwind v4 (no "use client", local cn,
 * uses CSS variable colours instead of dark: utility classes).
 */

import { motion, useScroll, useTransform } from 'motion/react';
import type { MotionValue } from 'motion/react';
import { useRef } from 'react';
import type { ComponentPropsWithoutRef, FC, ReactNode } from 'react';

import { cn } from './cn';

export interface TextRevealProps extends ComponentPropsWithoutRef<'div'> {
  children: string;
}

export const TextReveal: FC<TextRevealProps> = ({ children, className }) => {
  const sectionRef = useRef<HTMLDivElement | null>(null);
  const { scrollYProgress } = useScroll({ target: sectionRef });

  if (typeof children !== 'string') {
    throw new Error('TextReveal: children must be a string');
  }

  const words = children.split(' ');

  return (
    <div ref={sectionRef} className={cn('relative z-0 h-[200vh]', className)}>
      <div className="sticky top-0 mx-auto flex h-[50%] max-w-4xl items-center bg-transparent px-4 py-20">
        <span
          className="flex flex-wrap p-5 text-2xl font-bold text-[color:var(--text-muted)] opacity-20 md:p-8 md:text-3xl lg:p-10 lg:text-4xl xl:text-5xl"
          style={{ color: 'var(--text-muted)' }}
        >
          {words.map((word, i) => {
            const start = i / words.length;
            const end = start + 1 / words.length;
            return (
              <Word key={i} progress={scrollYProgress} range={[start, end]}>
                {word}
              </Word>
            );
          })}
        </span>
      </div>
    </div>
  );
};

interface WordProps {
  children: ReactNode;
  progress: MotionValue<number>;
  range: [number, number];
}

const Word: FC<WordProps> = ({ children, progress, range }) => {
  const opacity = useTransform(progress, range, [0, 1]);
  return (
    <span className="relative mx-1 lg:mx-1.5">
      <span className="absolute opacity-30">{children}</span>
      <motion.span style={{ opacity, color: 'var(--text)' }}>{children}</motion.span>
    </span>
  );
};
