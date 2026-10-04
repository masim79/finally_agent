import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  /** Right-aligned readout in the title bar: a count, a symbol, a timestamp. */
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

/**
 * Every instrument on the terminal wears the same chrome: a 24px title rail with a yellow
 * tick at its left edge, then the data. Consistent chrome is what makes a dense grid readable.
 */
export function Panel({ title, meta, children, className = "", bodyClassName = "" }: PanelProps) {
  return (
    <section
      className={`flex h-full min-h-0 w-full min-w-0 flex-col border border-line bg-surface ${className}`}
      aria-label={title}
    >
      <header className="flex h-6 shrink-0 items-center gap-2 border-b border-line bg-surface-2 pr-2">
        <span aria-hidden className="h-full w-[2px] bg-accent" />
        <h2 className="label text-ink-2">{title}</h2>
        {meta ? <div className="ml-auto flex items-center gap-2">{meta}</div> : null}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}

/** Shared treatment for "nothing here yet", so empty states look designed rather than broken. */
export function EmptyState({
  headline,
  hint,
  icon,
}: {
  headline: string;
  hint?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1.5 px-6 text-center">
      {icon ? <div className="mb-1 text-ink-3">{icon}</div> : null}
      <p className="label text-ink-2">{headline}</p>
      {hint ? <p className="max-w-[26ch] text-tiny leading-snug text-ink-3">{hint}</p> : null}
    </div>
  );
}
