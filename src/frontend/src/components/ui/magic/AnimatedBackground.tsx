/**
 * AnimatedBackground — reusable primitive from motion-primitives.
 * Renders an animated highlight that slides between child items.
 *
 * Usage: wrap clickable children that each have a `data-id` prop.
 */

import { AnimatePresence, motion } from 'motion/react';
import { Children, cloneElement, useEffect, useId, useState } from 'react';
import type { ReactElement } from 'react';
import type { Transition } from 'motion/react';

import { cn } from './cn';

export interface AnimatedBackgroundProps {
  children:
    | ReactElement<{ 'data-id': string }>[]
    | ReactElement<{ 'data-id': string }>;
  defaultValue?: string;
  onValueChange?: (newActiveId: string | null) => void;
  className?: string;
  transition?: Transition;
  enableHover?: boolean;
}

export function AnimatedBackground({
  children,
  defaultValue,
  onValueChange,
  className,
  transition,
  enableHover = false,
}: AnimatedBackgroundProps) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const uniqueId = useId();

  const handleSetActiveId = (id: string | null) => {
    setActiveId(id);
    onValueChange?.(id);
  };

  useEffect(() => {
    if (defaultValue !== undefined) {
      setActiveId(defaultValue);
    }
  }, [defaultValue]);

  return Children.map(children, (child: ReactElement<Record<string, unknown>>, index) => {
    const id = child.props['data-id'] as string;

    const interactionProps = enableHover
      ? {
          onMouseEnter: () => handleSetActiveId(id),
          onMouseLeave: () => handleSetActiveId(null),
        }
      : { onClick: () => handleSetActiveId(id) };

    return cloneElement(
      child,
      {
        key: index,
        className: cn('relative inline-flex', child.props.className as string | undefined),
        'data-checked': activeId === id ? 'true' : 'false',
        ...interactionProps,
      },
      <>
        <AnimatePresence initial={false}>
          {activeId === id && (
            <motion.div
              layoutId={`background-${uniqueId}`}
              className={cn('absolute inset-0', className)}
              transition={transition}
              initial={{ opacity: defaultValue ? 1 : 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            />
          )}
        </AnimatePresence>
        <div className="z-10">{child.props.children as React.ReactNode}</div>
      </>,
    );
  });
}
