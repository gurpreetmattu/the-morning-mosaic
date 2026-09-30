import { formatLongDate } from "./format";

/** Thin strip above the nameplate (DESIGN.md 8.1). Edition number is omitted when unknown. */
export function Dateline({
  editionNumber,
  width = "max-w-[1200px]",
  animate = false,
}: {
  editionNumber?: number;
  width?: string;
  /** Typewriter reveal on the first landing visit of a session (DESIGN.md 10 #1). */
  animate?: boolean;
}) {
  return (
    <div className="font-typewriter border-b border-ink text-sm text-ink-soft">
      <div
        className={`mx-auto flex flex-wrap items-center justify-between gap-x-4 px-4 py-1 sm:px-6 ${width}`}
      >
        <time className={animate ? "reveal-type" : undefined}>{formatLongDate()}</time>
        <span className="hidden sm:inline">
          Morning Edition &middot; Vol. I{editionNumber ? ` · No. ${editionNumber}` : ""}
        </span>
        <span>Price: Free</span>
      </div>
    </div>
  );
}
