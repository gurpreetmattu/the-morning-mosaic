import Link from "next/link";

const MOTTO = "Every line cited. Nothing invented.";

/**
 * Nameplate with ears (DESIGN.md 8.2). `full` is the landing/sample/archive
 * version; forms and settings pages use the compact bar.
 */
export function Masthead({
  tagline,
  weatherChip,
  variant = "full",
  width = "max-w-[1200px]",
}: {
  tagline: string;
  weatherChip?: string;
  variant?: "full" | "compact";
  width?: string;
}) {
  if (variant === "compact") {
    return (
      <div className="border-b-4 border-double border-ink">
        <div className={`mx-auto px-4 py-3 sm:px-6 ${width}`}>
          <Link href="/" className="font-mast text-[length:var(--fs-h2)] leading-none text-ink">
            The Morning Mosaic
          </Link>
        </div>
      </div>
    );
  }
  return (
    <div className="mx-auto max-w-[1200px] px-4 pt-6 sm:px-6">
      <div className="grid items-center gap-4 md:grid-cols-[1fr_auto_1fr]">
        <p className="kicker order-2 border-2 border-ink px-3 py-2 text-center md:order-1 md:justify-self-start">
          {weatherChip ?? "India"}
        </p>
        <h1 className="display-misreg font-mast order-1 text-center text-[length:var(--fs-masthead)] leading-[0.95] font-normal tracking-[-0.01em] md:order-2">
          The Morning Mosaic
        </h1>
        <p className="font-head order-3 border-2 border-ink px-3 py-2 text-center text-sm italic md:justify-self-end">
          {MOTTO}
        </p>
      </div>
      <div className="mt-4 border-t-4 border-ink" />
      <div className="flex flex-wrap items-center justify-between gap-x-4 py-2 text-sm">
        <p className="font-head italic">{tagline}</p>
        <p className="kicker text-ink-soft">
          Est. 2026 &middot; Morning Edition &middot; 6&ndash;9 AM IST
        </p>
      </div>
      <div className="border-t-4 border-double border-ink" />
    </div>
  );
}
