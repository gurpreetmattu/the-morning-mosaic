"use client";

import { useId } from "react";

/**
 * Native radio group styled as chips or ticket stubs (DESIGN.md 8.5).
 * Radios stay real inputs, so arrow keys, form semantics and screen readers
 * work without ARIA. `stub` variant is the time "departure board" ticket.
 */
export function ChoiceGroup({
  legend,
  helper,
  options,
  value,
  onChange,
  variant = "chip",
}: {
  legend: string;
  helper?: string;
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
  variant?: "chip" | "stub";
}) {
  const name = useId();
  const box =
    variant === "stub"
      ? "font-figures min-w-24 px-4 py-3 text-center text-lg font-bold"
      : "font-gothic px-4 py-3 text-base font-semibold";
  return (
    <fieldset className="mb-6">
      <legend className="kicker mb-1 text-ink">{legend}</legend>
      {helper && <p className="font-gothic mb-2 text-sm text-ink-soft">{helper}</p>}
      <div className="flex flex-wrap gap-3">
        {options.map((option) => (
          <label key={option.value} className="cursor-pointer">
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="peer sr-only"
            />
            <span
              className={`block min-h-11 border-2 border-ink bg-paper-raised text-ink shadow-[var(--block-1)] transition-transform peer-checked:bg-ink peer-checked:text-paper peer-checked:shadow-none peer-focus-visible:outline-3 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-ink ${box}`}
            >
              {option.label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
