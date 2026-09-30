/**
 * Live "Your edition" preview (DESIGN.md 9.2): updates as the reader chooses.
 * Purely a summary of the form state, no data of its own.
 */
export function EditionSummary({
  genres,
  cityName,
  timeLabel,
  frequencyLabel,
}: {
  genres: { key: string; name: string }[];
  cityName: string | null;
  timeLabel: string;
  frequencyLabel: string;
}) {
  return (
    <aside
      aria-label="Your edition"
      className="border-2 border-ink bg-paper-raised p-5 shadow-[var(--block-2)]"
    >
      <p className="kicker text-ink-soft">Your edition</p>
      <p className="font-mast mt-1 text-2xl leading-none">The Morning Mosaic</p>
      <div className="mt-3 border-y-4 border-double border-ink py-3">
        {genres.length === 0 ? (
          <p className="font-typewriter text-sm text-ink-soft">No genres chosen yet.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {genres.map((g) => (
              <li
                key={g.key}
                data-genre={g.key}
                className="kicker font-slab border-2 border-genre bg-genre-tint px-2 py-1 text-genre"
              >
                {g.name}
              </li>
            ))}
          </ul>
        )}
      </div>
      <dl className="font-gothic mt-3 space-y-1 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-ink-soft">Weather for</dt>
          <dd className="font-semibold">{cityName ?? "Not chosen yet"}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-ink-soft">Arrives around</dt>
          <dd className="font-figures font-bold">{timeLabel}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-ink-soft">How often</dt>
          <dd className="font-semibold">{frequencyLabel}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-ink-soft">Stories</dt>
          <dd className="font-semibold">
            {genres.length === 0 ? "4–6 per genre" : `${genres.length * 4}–${genres.length * 6}`}
          </dd>
        </div>
      </dl>
    </aside>
  );
}
