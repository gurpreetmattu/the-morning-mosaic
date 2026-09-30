/**
 * Step header as a ticket stub (DESIGN.md 8.6): perforated left edge,
 * "ADMIT ONE" micro-label, big numeral. The heading is a real h2 that
 * receives focus on step change (tabIndex -1, focused by the caller).
 */
export function StepTicket({
  step,
  total,
  name,
  title,
  headingRef,
}: {
  step: number;
  total: number;
  name: string;
  title: string;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
}) {
  return (
    <div className="mb-6 flex items-stretch border-2 border-ink bg-paper-raised shadow-[var(--block-1)]">
      <div className="flex flex-col items-center justify-center border-e-2 border-dashed border-ink px-4 py-3">
        <span className="font-typewriter text-[0.65rem] leading-none text-ink-soft">ADMIT ONE</span>
        <span aria-hidden className="font-mast text-5xl leading-none">
          {step}
        </span>
      </div>
      <div className="flex-1 px-4 py-3">
        <p className="kicker text-ink-soft">
          Step {step} of {total}: {name}
        </p>
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="font-head text-[length:var(--fs-h3)] leading-tight outline-none"
        >
          {title}
        </h2>
      </div>
    </div>
  );
}
