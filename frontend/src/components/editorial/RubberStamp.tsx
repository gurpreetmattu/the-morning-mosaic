import type { ReactNode } from "react";

/**
 * Rubber stamp (DESIGN.md 8.13). Real text inside, so it is readable by
 * assistive tech and never the only carrier of state. Rotation is decorative
 * and stays within -6..+4 degrees.
 */
export function RubberStamp({
  children,
  tone = "red",
  size = "small",
  rotate = -4,
  className = "",
}: {
  children: ReactNode;
  tone?: "red" | "ink" | "genre";
  size?: "small" | "large";
  rotate?: number;
  className?: string;
}) {
  const color =
    tone === "red"
      ? "text-press-red border-press-red"
      : tone === "genre"
        ? "text-genre border-genre"
        : "text-ink border-ink";
  const scale = size === "large" ? "px-4 py-2 text-2xl" : "px-2 py-1 text-xs";
  return (
    <span
      className={`font-slab inline-block border-[3px] border-double tracking-[0.08em] uppercase ${color} ${scale} ${className}`}
      style={{ transform: `rotate(${rotate}deg)` }}
    >
      {children}
    </span>
  );
}
