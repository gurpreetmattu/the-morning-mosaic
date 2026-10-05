import Link from "next/link";
import { GENRES } from "@/content/genres";
import type { LatestHighlights } from "@/lib/types";
import { formatLongDate } from "./format";

const genreName = (slug: string) => GENRES.find((g) => g.slug === slug)?.name ?? slug;

/**
 * Hero component built from the newest published edition: real, cited and
 * checked, so it carries no "Sample" label. Each item links to the full
 * edition, where every sentence has its sources.
 */
export function LatestPreview({ latest }: { latest: LatestHighlights }) {
  const href = `/editions/${latest.edition_date}`;
  const date = formatLongDate(new Date(`${latest.edition_date}T12:00:00+05:30`));

  return (
    <figure
      className="preview-unfold relative mx-auto w-full max-w-[720px] lg:rotate-[-1deg] lg:transition-transform lg:hover:rotate-0"
      aria-label={`Latest edition, ${date}`}
    >
      <div className="relative border-2 border-ink bg-paper-raised p-5 shadow-[var(--block-2)] sm:p-6">
        <div className="border-b-4 border-double border-ink pb-3 text-center">
          <p className="font-typewriter text-xs text-ink-soft">
            Morning Edition &middot; No. {latest.edition_number}
          </p>
          <p className="font-mast text-3xl leading-none sm:text-4xl">The Morning Mosaic</p>
          <p className="font-typewriter mt-1 text-xs text-ink-soft">{date}</p>
        </div>

        <div className="mt-4 space-y-4">
          {latest.items.map((item) => (
            <article key={item.genre} data-genre={item.genre}>
              <p className="kicker text-genre">{genreName(item.genre)}</p>
              <h3 className="font-head text-lg leading-tight">{item.headline}</h3>
              <p className="mt-1 text-sm leading-snug">{item.one_liner}</p>
            </article>
          ))}
        </div>

        <p className="font-gothic mt-4 border-t border-dotted border-ink pt-3 text-sm font-semibold">
          <Link href={href} className="underline">
            Read the full edition, with sources &rarr;
          </Link>
        </p>
      </div>
      <figcaption className="font-typewriter mt-3 text-center text-sm text-ink-soft">
        From the latest edition.
      </figcaption>
    </figure>
  );
}
