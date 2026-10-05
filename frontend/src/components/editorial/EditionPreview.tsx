import sample from "../../../fixtures/sample-edition.json";
import { Citation } from "./Citation";
import { RubberStamp } from "./RubberStamp";

const source = (n: number) => sample.sources.find((s) => s.n === n)!;

/**
 * Hero component (DESIGN.md 8.7): a mini front page built from
 * fixtures/sample-edition.json, always labelled Sample. Only shown before the
 * first real edition is published (see HeroPreview); the stamp is never removed here.
 */
export function EditionPreview() {
  return (
    <figure
      className="preview-unfold relative mx-auto w-full max-w-[720px] lg:rotate-[-1deg] lg:transition-transform lg:hover:rotate-0"
      aria-label={sample.label}
    >
      <div className="relative border-2 border-ink bg-paper-raised p-5 shadow-[var(--block-2)] sm:p-6">
        <div className="border-b-4 border-double border-ink pb-3 text-center">
          <p className="font-typewriter text-xs text-ink-soft">Morning Edition</p>
          <p className="font-mast text-3xl leading-none sm:text-4xl">The Morning Mosaic</p>
        </div>

        <div className="font-gothic mt-3 flex flex-wrap items-center justify-between gap-2 border-b border-ink pb-2 text-xs">
          <span className="border border-ink px-2 py-1">
            {sample.weather.city} &middot; {sample.weather.temperature}&deg;C &middot;{" "}
            {sample.weather.condition}
          </span>
          <span className="font-figures border-y border-dotted border-ink px-2 py-1">
            {sample.market.label} {sample.market.value} ({sample.market.note})
          </span>
        </div>

        <section className="mt-4 border-2 border-ink p-3 shadow-[var(--block-1)]">
          <p className="kicker mb-1 flex items-center gap-2">
            <span className="font-slab text-press-red">Stop press</span>
            <span>60-second summary</span>
          </p>
          <ul className="font-head list-disc space-y-1 ps-5 text-[0.95rem]">
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

        <div className="mt-4 grid gap-4 sm:grid-cols-2 sm:divide-x sm:divide-rule-soft">
          {sample.stories.map((story, i) => (
            <article key={story.headline} data-genre={story.genre} className={i ? "sm:ps-4" : ""}>
              <p className="kicker text-genre">{story.kicker}</p>
              <h3 className="font-head text-lg leading-tight">{story.headline}</h3>
              <p className="mt-1 text-sm leading-snug">
                {story.body}
                <Citation
                  n={story.cite}
                  source={source(story.cite).name}
                  time={source(story.cite).time}
                  sample
                />
              </p>
            </article>
          ))}
        </div>

        <ol className="font-gothic mt-4 border-t border-dotted border-ink pt-2 text-xs text-ink-soft">
          {sample.sources.map((s) => (
            <li key={s.n}>
              {s.n}. {s.name}, {s.time}
            </li>
          ))}
        </ol>
      </div>

      <div className="pointer-events-none absolute -top-3 -right-2 sm:-right-4">
        <RubberStamp size="large" rotate={-6}>
          Sample
        </RubberStamp>
      </div>
      <figcaption className="font-typewriter mt-3 text-center text-sm text-ink-soft">
        {sample.label}
      </figcaption>
    </figure>
  );
}
