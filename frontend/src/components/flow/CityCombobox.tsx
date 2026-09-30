"use client";

import { useId, useMemo, useState } from "react";
import type { CityOption } from "@/lib/types";

const MAX_RESULTS = 8;

const label = (city: CityOption) => `${city.name}, ${city.state}`;

/**
 * ARIA combobox over the validated city list (DESIGN.md 8.5). The value is a
 * city id, and it is only ever set by choosing a listed city, so free text
 * can never reach the API. Arrows move, Enter chooses, Esc closes.
 */
export function CityCombobox({
  cities,
  value,
  onChange,
  inputId,
  invalid = false,
  describedBy,
}: {
  cities: CityOption[];
  value: string;
  onChange: (cityId: string) => void;
  inputId: string;
  invalid?: boolean;
  describedBy?: string;
}) {
  const base = useId();
  const listId = `${base}-list`;
  const selected = cities.find((c) => c.id === value);
  const [query, setQuery] = useState(selected ? label(selected) : "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const pool = q ? cities.filter((c) => label(c).toLowerCase().includes(q)) : cities;
    return pool.slice(0, MAX_RESULTS);
  }, [cities, query]);

  function choose(city: CityOption) {
    setQuery(label(city));
    onChange(city.id);
    setOpen(false);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && open && results[active]) {
      e.preventDefault(); // choosing a city must not submit the form
      choose(results[active]);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      setOpen(false);
    }
  }

  return (
    <div className="relative">
      <input
        id={inputId}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && results[active] ? `${base}-opt-${active}` : undefined}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        autoComplete="off"
        spellCheck={false}
        value={query}
        placeholder="Start typing a city"
        onChange={(e) => {
          setQuery(e.target.value);
          setActive(0);
          setOpen(true);
          if (value) onChange(""); // typing again un-chooses the previous city
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        className={`font-gothic min-h-12 w-full rounded-none border-2 bg-paper-raised px-3 py-2 text-base text-ink focus:shadow-[var(--block-genre)] ${invalid ? "border-danger" : "border-ink"}`}
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          aria-label="Cities"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto border-2 border-ink bg-paper-raised shadow-[var(--block-1)]"
        >
          {results.length === 0 && (
            <li className="font-typewriter px-3 py-2 text-sm text-ink-soft">
              No match. Try the nearest big city.
            </li>
          )}
          {results.map((city, i) => (
            <li
              key={city.id}
              id={`${base}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              // mousedown, not click: fires before the input's blur closes the list.
              onMouseDown={(e) => {
                e.preventDefault();
                choose(city);
              }}
              onMouseEnter={() => setActive(i)}
              className={`font-gothic flex min-h-11 cursor-pointer items-baseline px-3 py-2 ${i === active ? "bg-ink text-paper" : ""}`}
            >
              <span className="font-semibold">{city.name}</span>
              <span aria-hidden className="mx-2 flex-1 border-b-2 border-dotted border-current" />
              <span className="text-sm">{city.state}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
