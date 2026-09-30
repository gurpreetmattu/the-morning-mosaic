"use client";

import Link from "next/link";
import { useState } from "react";
import { GENRES } from "@/content/genres";
import { GenreCard } from "./GenreCard";

/**
 * The landing "stamp sheet": pick genres here and carry them into the
 * subscribe flow through the query string. Nothing is stored.
 */
export function StampSheet() {
  const [selected, setSelected] = useState<string[]>([]);
  const query = selected.length ? `?genres=${selected.join(",")}` : "";

  return (
    <div>
      <fieldset>
        <legend className="sr-only">Choose your genres</legend>
        <div className="grid grid-cols-2 gap-5 sm:grid-cols-3 xl:grid-cols-5">
          {GENRES.map((g, i) => (
            <GenreCard
              key={g.slug}
              genre={g.slug}
              name={g.name}
              blurb={g.blurb}
              numeral={i + 1}
              checked={selected.includes(g.slug)}
              onChange={(on) =>
                setSelected((cur) => (on ? [...cur, g.slug] : cur.filter((s) => s !== g.slug)))
              }
            />
          ))}
        </div>
      </fieldset>
      <p aria-live="polite" className="font-gothic mt-6 text-sm">
        {selected.length === 0
          ? "Pick at least one. Each genre brings 4–6 stories."
          : `${selected.length} genre${selected.length === 1 ? "" : "s"} chosen.`}
      </p>
      <Link
        href={`/subscribe${query}`}
        className="font-gothic mt-3 inline-block min-h-12 border-2 border-ink bg-ink px-5 py-3 text-base font-bold tracking-[0.06em] text-paper uppercase shadow-[var(--block-1)] hover:opacity-90"
      >
        Start my edition
      </Link>
    </div>
  );
}
