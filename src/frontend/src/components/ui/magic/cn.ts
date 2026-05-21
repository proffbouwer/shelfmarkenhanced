/**
 * Lightweight class-name concatenator for Magic UI components.
 * Filters out falsy values and joins with a space — no external dependency needed.
 */
export function cn(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ');
}
