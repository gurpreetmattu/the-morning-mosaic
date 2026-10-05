"use client";

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";

/**
 * Citation marker + source popover (DESIGN.md 8.8). A real button; the
 * popover is an "index card". Every story also prints its numbered source
 * list, so nothing depends on JavaScript or hover.
 */
export function Citation({
  n,
  source,
  time,
  sample = false,
}: {
  n: number;
  source: string;
  time: string;
  sample?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLSpanElement>(null);
  const popover = useRef<HTMLSpanElement>(null);
  const id = useId();

  // Nudge the card sideways if it would run off either edge of a narrow screen.
  useLayoutEffect(() => {
    const el = popover.current;
    if (!open || !el) return;
    el.style.transform = "";
    const { left, right } = el.getBoundingClientRect();
    const margin = 8;
    const overflowRight = right - (document.documentElement.clientWidth - margin);
    const overflowLeft = margin - left;
    if (overflowRight > 0) el.style.transform = `translateX(${-overflowRight}px)`;
    else if (overflowLeft > 0) el.style.transform = `translateX(${overflowLeft}px)`;
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  return (
    <span ref={wrap} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        aria-label={`Source ${n}: ${source}`}
        onClick={() => setOpen((o) => !o)}
        className="font-figures mx-0.5 inline-grid size-6 -translate-y-1 place-items-center rounded-full border border-genre align-super text-xs leading-none font-bold text-genre hover:bg-genre-tint"
      >
        {n}
      </button>
      {open && (
        <span
          ref={popover}
          id={id}
          role="dialog"
          aria-label={`Source ${n}`}
          className="font-gothic absolute start-0 top-full z-20 mt-1 block w-64 max-w-[calc(100vw-1rem)] border-2 border-ink bg-paper-raised p-3 text-start text-sm font-normal shadow-[var(--block-1)]"
        >
          <span className="kicker block text-ink">{source}</span>
          <span className="font-figures block text-ink-soft">{time}</span>
          <span className="mt-1 block text-ink-soft">
            {sample ? "Sample source. Not a real link." : "Quoted from the source text."}
          </span>
        </span>
      )}
    </span>
  );
}
