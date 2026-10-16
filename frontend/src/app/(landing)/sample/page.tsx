import Link from "next/link";
import sample from "../../../../fixtures/sample-edition.json";
import { Citation } from "@/components/editorial/Citation";
import { RubberStamp } from "@/components/editorial/RubberStamp";

export const metadata = { title: "Sample edition" };

const source = (n: number) => sample.sources.find((s) => s.n === n)!;

/**
 * The web version of a sample edition (DESIGN.md 9.7). Built from the same
 * fixture as the landing preview, so the two cannot drift. Printable: the
 * print stylesheet drops the site chrome and starts each genre on a new page.
 */
export default function SamplePage() {
  return (
    <article className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <p className="no-print font-gothic mb-6 text-sm font-semibold">
        <Link href="/" className="underline">
          &larr; Back to the front page
        </Link>
      </p>
      <div className="no-print mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="kicker text-ink-soft">Web version</p>
          <h2 className="font-head text-[length:var(--fs-h2)] leading-tight">Sample edition</h2>
        </div>
        <RubberStamp size="large" rotate={-5}>
          Sample
        </RubberStamp>
      </div>
      <p className="font-typewriter mb-8 text-sm text-ink-soft">
        {sample.label} Everything below is invented to show the layout; a real edition is written
        only from fetched, cited sources.
      </p>

      <div className="font-gothic mb-6 flex flex-wrap items-center justify-between gap-2 border-y border-ink py-2 text-sm">
        <span>
          {sample.weather.city} &middot; {sample.weather.temperature}&deg;C &middot;{" "}
          {sample.weather.condition}
        </span>
        <span className="font-figures">
          {sample.market.label} {sample.market.value} ({sample.market.note})
        </span>
      </div>

      <section className="mb-10 border-2 border-ink bg-paper-raised p-5 shadow-[var(--block-1)]">
        <p className="kicker mb-2 flex items-center gap-2">
          <span className="font-slab text-press-red">Stop press</span>
          <span>Today in 60 seconds</span>
        </p>
        <ul className="font-head list-disc space-y-2 ps-5 text-lg">
          {sample.summary.map((item) => (
            <li key={item.text}>
              {item.text}
              <Citation
                n={item.cite}
                source={source(item.cite).name}
                time={source(item.cite).time}
                sample
              />
            </li>
          ))}
        </ul>
      </section>

      {sample.sections.map((section) => (
        <section
          key={section.genre}
          data-genre={section.genre}
          className="print-page mb-10 border-t-4 border-genre pt-4"
        >
          <span aria-hidden className={`motif motif-${section.genre} mb-3`} />
          <h3 className="kicker font-slab mb-4 text-genre">{section.title}</h3>
          <div className="space-y-6">
            {section.stories.map((story) => (
              <div key={story.headline}>
                <h4 className="font-head text-[length:var(--fs-headline)] leading-tight">
                  {story.headline}
                </h4>
                <p className="mt-1 max-w-[65ch]">
                  {story.body}
                  <Citation
                    n={story.cite}
                    source={source(story.cite).name}
                    time={source(story.cite).time}
                    sample
                  />
                </p>
              </div>
            ))}
          </div>
        </section>
      ))}

      <section className="mb-10 border-t border-dotted border-ink pt-4">
        <h3 className="kicker mb-2">Sources</h3>
        <ol className="font-gothic space-y-1 text-sm text-ink-soft">
          {sample.sources.map((s) => (
            <li key={s.n}>
              {s.n}. {s.name}, {s.time}. Sample source, not a real link.
            </li>
          ))}
        </ol>
      </section>

      <div className="no-print flex flex-wrap gap-4">
        <Link
          href="/subscribe"
          className="font-gothic inline-block min-h-12 border-2 border-ink bg-ink px-6 py-3 text-base font-bold tracking-[0.06em] text-paper uppercase shadow-[var(--block-1)]"
        >
          Start my edition
        </Link>
        <Link
          href="/how-we-report"
          className="font-gothic inline-block min-h-12 border-2 border-ink bg-paper-raised px-6 py-3 text-base font-bold tracking-[0.06em] uppercase shadow-[var(--block-1)]"
        >
          How we report
        </Link>
      </div>
    </article>
  );
}
