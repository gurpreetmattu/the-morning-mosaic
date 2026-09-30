"use client";

import { useState } from "react";

/**
 * Split-flap readout (DESIGN.md 10 #7): one cell per character, and a cell flips only when its
 * character changes. Purely visual, so it is aria-hidden; callers pair it with real text for
 * assistive tech (the page keeps a visually hidden "Arrives around ..." sentence).
 * Nothing flips on first render, only on later changes; prefers-reduced-motion removes the flip.
 */
export function SplitFlap({ text }: { text: string }) {
  // The previous value is kept in state and updated while rendering, which is React's
  // supported way to derive "what changed" from props without reading a ref during render.
  const [tracked, setTracked] = useState({ text, previous: text });
  if (tracked.text !== text) setTracked({ text, previous: tracked.text });

  const before = [...tracked.previous];
  return (
    <span aria-hidden className="inline-flex flex-wrap gap-1">
      {[...text].map((char, i) => (
        <span
          // Including the character in the key remounts a changed cell, which replays its flip.
          key={`${i}-${char}`}
          className={`flap ${before[i] !== char ? "flap-anim" : ""}`}
        >
          {char === " " ? " " : char}
        </span>
      ))}
    </span>
  );
}
