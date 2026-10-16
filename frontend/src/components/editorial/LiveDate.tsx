"use client";

import { useSyncExternalStore } from "react";
import { liveDateText } from "./format";

const noopSubscribe = () => () => {};

/**
 * Today's date (or year), correct in the reader's browser even when the page was prerendered
 * days ago. Static pages bake the build-time date into their HTML. The server component passes
 * that same value as `initial`, so hydration matches the HTML exactly; React then re-renders
 * with the live value. (Reading the live date during hydration instead would leave the stale
 * text on screen: React keeps server text when it differs under suppressHydrationWarning.)
 */
export function LiveDate({
  initial,
  kind = "long",
  className,
}: {
  initial: string;
  kind?: "long" | "year";
  className?: string;
}) {
  const text = useSyncExternalStore(
    noopSubscribe,
    () => liveDateText(kind),
    () => initial,
  );
  const Tag = kind === "year" ? "span" : "time";
  return <Tag className={className}>{text}</Tag>;
}
