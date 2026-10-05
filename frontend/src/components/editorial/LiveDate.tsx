"use client";

import { useSyncExternalStore } from "react";
import { formatLongDate } from "./format";

const noopSubscribe = () => () => {};

/**
 * Today's date (or year), correct in the reader's browser even when the page was prerendered
 * days ago. Static pages bake the build-time date into their HTML; React uses the server value
 * only for hydration and then switches to the live one, so there is no mismatch warning.
 */
export function LiveDate({
  kind = "long",
  className,
}: {
  kind?: "long" | "year";
  className?: string;
}) {
  const read = () => (kind === "year" ? String(new Date().getFullYear()) : formatLongDate());
  const text = useSyncExternalStore(noopSubscribe, read, read);
  const Tag = kind === "year" ? "span" : "time";
  return (
    <Tag className={className} suppressHydrationWarning>
      {text}
    </Tag>
  );
}
