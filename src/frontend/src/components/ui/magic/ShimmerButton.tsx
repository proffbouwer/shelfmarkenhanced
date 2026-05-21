/**
 * ShimmerButton — a button with a rotating shimmer highlight on its border.
 *
 * Requires the keyframe animations `shimmer-slide` and `spin-around` to be
 * declared in your global CSS (see index.css magic-ui section).
 *
 * Adapted from magicui.design for Tailwind v4 (no "use client", local cn).
 */

import React from 'react';
import type { ComponentPropsWithoutRef, CSSProperties } from 'react';

import { cn } from './cn';

export interface ShimmerButtonProps extends ComponentPropsWithoutRef<'button'> {
  shimmerColor?: string;
  shimmerSize?: string;
  borderRadius?: string;
  shimmerDuration?: string;
  background?: string;
  className?: string;
  children?: React.ReactNode;
}

export const ShimmerButton = React.forwardRef<HTMLButtonElement, ShimmerButtonProps>(
  (
    {
      shimmerColor = 'var(--accent)',
      shimmerSize = '0.05em',
      shimmerDuration = '3s',
      borderRadius = '8px',
      background = 'var(--bg-soft)',
      className,
      children,
      ...props
    },
    ref,
  ) => {
    return (
      <button
        style={
          {
            '--spread': '90deg',
            '--shimmer-color': shimmerColor,
            '--radius': borderRadius,
            '--speed': shimmerDuration,
            '--cut': shimmerSize,
            '--bg': background,
          } as CSSProperties
        }
        className={cn(
          'group relative z-0 flex cursor-pointer items-center justify-center overflow-hidden whitespace-nowrap',
          'border border-(--border-muted) px-4 py-2 text-sm font-medium',
          '[border-radius:var(--radius)] [background:var(--bg)]',
          'transform-gpu transition-transform duration-300 ease-in-out active:translate-y-px',
          className,
        )}
        ref={ref}
        {...props}
      >
        {/* spark container */}
        <div className="absolute inset-0 -z-30 overflow-visible blur-[2px]">
          <div className="animate-shimmer-slide absolute inset-0 aspect-square h-full rounded-none">
            <div className="animate-spin-around absolute -inset-full rotate-0 [background:conic-gradient(from_calc(270deg-(var(--spread)*0.5)),transparent_0,var(--shimmer-color)_var(--spread),transparent_var(--spread))]" />
          </div>
        </div>

        {children}

        {/* inner highlight */}
        <div
          className={cn(
            'absolute inset-0 size-full rounded-[inherit]',
            'shadow-[inset_0_-8px_10px_color-mix(in_srgb,var(--shimmer-color)_12%,transparent)]',
            'transition-all duration-300 ease-in-out',
            'group-hover:shadow-[inset_0_-6px_10px_color-mix(in_srgb,var(--shimmer-color)_25%,transparent)]',
            'group-active:shadow-[inset_0_-10px_10px_color-mix(in_srgb,var(--shimmer-color)_25%,transparent)]',
          )}
        />

        {/* backdrop that cuts out the shimmer from the fill area */}
        <div className="absolute -z-20 [inset:var(--cut)] [border-radius:var(--radius)] [background:var(--bg)]" />
      </button>
    );
  },
);

ShimmerButton.displayName = 'ShimmerButton';
