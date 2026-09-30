"use client";

import { useId } from "react";

/**
 * Genre "postage stamp" (DESIGN.md 8.4). A native checkbox inside a label,
 * so keyboard, screen readers and forms work without extra ARIA.
 * `genre` sets data-genre so the card reads --g-accent / --g-tint.
 */
export function GenreCard({
  genre,
  name,
  blurb,
  numeral,
  checked,
  onChange,
}: {
  genre: string;
  name: string;
  blurb: string;
  numeral: number;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const id = useId();
  return (
    <label htmlFor={id} data-genre={genre} className="stamp-card block h-full cursor-pointer">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="peer sr-only"
      />
      <span className="stamp-face relative block h-full min-h-32">
        <span
          className="font-figures absolute bottom-3 left-4 text-2xl font-bold text-genre"
          aria-hidden
        >
          {numeral}
        </span>
        <span aria-hidden className={`motif motif-${genre} mb-3`} />
        <span className="kicker font-slab mb-2 block text-genre">{name}</span>
        <span className="block pb-12 text-sm leading-snug text-ink">{blurb}</span>
        {checked && (
          <span
            aria-hidden
            className="postmark font-slab absolute right-3 bottom-3 grid size-11 place-items-center rounded-full border-2 border-genre bg-paper-raised text-xs text-genre"
          >
            IN
          </span>
        )}
        <span className="sr-only">{checked ? "Selected" : "Not selected"}</span>
      </span>
    </label>
  );
}
