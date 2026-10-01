import Link from "next/link";
import { Citation } from "@/components/editorial/Citation";
import { EditionPreview } from "@/components/editorial/EditionPreview";
import { RubberStamp } from "@/components/editorial/RubberStamp";
import { StampSheet } from "@/components/editorial/StampSheet";
import { StickyCta } from "@/components/editorial/StickyCta";
import { SUPPORTING_LINE, TAGLINE } from "@/content/brand";
import { LIVE_GENRE_COUNT_WORD } from "@/content/genres";

const primaryCta =
  "font-gothic inline-block min-h-12 border-2 border-ink bg-ink px-6 py-3 text-base font-bold tracking-[0.06em] text-paper uppercase shadow-[var(--block-1)] transition-transform hover:-translate-x-px hover:-translate-y-px active:translate-x-[3px] active:translate-y-[3px] active:shadow-none";
const secondaryCta =
  "font-gothic inline-block min-h-12 border-2 border-ink bg-paper-raised px-6 py-3 text-base font-bold tracking-[0.06em] text-ink uppercase shadow-[var(--block-1)] transition-transform hover:-translate-x-px hover:-translate-y-px active:translate-x-[3px] active:translate-y-[3px] active:shadow-none";

const STEPS = [
  {
    n: "1",
    title: "Pick your genres",
    text: `Choose from ${LIVE_GENRE_COUNT_WORD}. Each brings 4–6 stories.`,
  },
  {
    n: "2",
    title: "Choose city and time",
    text: "Your city sets the weather. Pick any half hour from 6:00 to 9:00 AM IST.",
  },
  {
    n: "3",
    title: "Read your edition",
    text: "One email every morning, with an A4 PDF if you want to print it.",
  },
];

const ANATOMY = [
  "Nameplate, date and edition number",
  "Weather for your city",
  "A USD/INR strip, with the time of its data",
  "Today in 60 seconds",
  "4–6 cited stories for each genre you chose",
  "Extras: scores, releases and a quote of the day",
  "A downloadable A4 PDF",
  "Longer reads on Saturday, a weekly recap on Sunday",
];

const FAQ = [
  {
    q: "What does it cost?",
    a: "Nothing. Editions are free.",
  },
  {
    q: "Which sources do you use?",
    a: "A fixed list of publisher feeds and news services. We don't pull from anywhere else, and we skip paywalled pages.",
  },
  {
    q: "Is the AI making things up?",
    a: "AI helps us summarise. Every sentence is checked against its source. If we can't verify a story, we drop it.",
  },
  {
    q: "What if an edition is late?",
    a: "We'd rather be late than wrong. If your edition can't be sent, we email you a short apology instead.",
  },
  {
    q: "Can I change my genres?",
    a: "Yes, any time. Use Manage subscription and we'll email you a sign-in link. No password.",
  },
  {
    q: "How do I unsubscribe?",
    a: "Every email has an unsubscribe link. One click and you're off the list.",
  },
  {
    q: "What do you do with my email?",
    a: "We use it to send your edition. We keep your name, email, city, genres and delivery time, and nothing else.",
  },
];

function SectionHeading({ kicker, children }: { kicker: string; children: React.ReactNode }) {
  return (
    <div className="mb-8">
      <p className="kicker mb-2 text-ink-soft">{kicker}</p>
      <h2 className="font-head text-[length:var(--fs-h2)] leading-[1.15]">{children}</h2>
    </div>
  );
}

export default function HomePage() {
  return (
    <>
      {/* Stop-press strip: static, not a marquee. */}
      <div className="border-b border-ink bg-paper-sunk">
        <p className="font-gothic mx-auto flex max-w-[1200px] items-center gap-3 px-4 py-2 text-sm sm:px-6">
          <span className="font-slab text-xs tracking-[0.08em] text-press-red uppercase">
            Stop press
          </span>
          Now printing: the morning edition, set to your interests.
        </p>
      </div>

      {/* Hero */}
      <section id="hero" className="mx-auto max-w-[1200px] px-4 py-12 sm:px-6 lg:py-16">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <div>
            <h2 className="font-mast text-[length:var(--fs-display)] leading-[1.05] font-normal tracking-[-0.01em]">
              {TAGLINE}
            </h2>
            <p className="mt-4 max-w-[52ch] text-lg text-ink-soft">{SUPPORTING_LINE}</p>
            <div className="mt-6 flex flex-wrap gap-4">
              <Link href="/subscribe" className={primaryCta}>
                Start my edition
              </Link>
              <Link href="/sample" className={secondaryCta}>
                See a sample edition
              </Link>
            </div>
            <p className="font-typewriter mt-4 text-sm text-ink-soft">
              Free. 6&ndash;9 AM IST. Unsubscribe in one click.
            </p>
          </div>
          <EditionPreview />
        </div>
      </section>

      {/* How it works */}
      <section className="border-y-4 border-double border-ink bg-paper-sunk">
        <div className="mx-auto max-w-[1200px] px-4 py-12 sm:px-6">
          <p className="kicker mb-6 text-ink-soft">Pick &middot; Choose &middot; Read</p>
          <ol className="grid gap-6 md:grid-cols-3">
            {STEPS.map((s) => (
              <li
                key={s.n}
                className="relative border-2 border-ink bg-paper-raised p-5 ps-6 shadow-[var(--block-1)]"
              >
                <p className="font-typewriter text-xs text-ink-soft">ADMIT ONE</p>
                <p className="font-mast text-5xl leading-none" aria-hidden>
                  {s.n}
                </p>
                <h3 className="font-head mt-2 text-xl">{s.title}</h3>
                <p className="mt-1 text-sm text-ink-soft">{s.text}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Stamp sheet */}
      <section id="genres" className="mx-auto max-w-[1200px] px-4 py-16 sm:px-6">
        <SectionHeading kicker="The genres">
          {LIVE_GENRE_COUNT_WORD.charAt(0).toUpperCase() + LIVE_GENRE_COUNT_WORD.slice(1)} genres.
          Your mix.
        </SectionHeading>
        <StampSheet />
      </section>

      {/* Anatomy of an edition */}
      <section id="inside" className="defer-render border-y border-ink bg-paper-sunk">
        <div className="mx-auto max-w-[1200px] px-4 py-16 sm:px-6">
          <SectionHeading kicker="What's inside">One email, everything in it</SectionHeading>
          <ol className="font-gothic grid gap-x-10 gap-y-3 sm:grid-cols-2">
            {ANATOMY.map((item, i) => (
              <li
                key={item}
                className="flex items-baseline gap-3 border-b border-dotted border-ink pb-2"
              >
                <span className="font-figures text-sm font-bold text-press-red" aria-hidden>
                  {i + 1}
                </span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Trust */}
      <section id="trust" className="defer-render mx-auto max-w-[1200px] px-4 py-16 sm:px-6">
        <SectionHeading kicker="How we report">Grounded, not invented</SectionHeading>
        <div className="grid gap-6 md:grid-cols-3">
          <article className="border-2 border-ink bg-paper-raised p-5 shadow-[var(--block-1)]">
            <h3 className="font-head text-xl">Every sentence cites a source</h3>
            <p className="mt-2 text-sm text-ink-soft">
              A citation is a link to the exact source of a sentence. Try one:
            </p>
            <p className="font-head mt-3 border-s-4 border-highlight ps-3">
              This sentence is an example
              <Citation n={1} source="Example source" time="6:00 AM IST" sample />
            </p>
          </article>
          <article className="border-2 border-ink bg-paper-raised p-5 shadow-[var(--block-1)]">
            <h3 className="font-head text-xl">Every claim is checked</h3>
            <p className="mt-2 text-sm text-ink-soft">
              A second pass checks each claim against the source text. Numbers, dates and names are
              also checked by code, not by the AI.
            </p>
            <div className="mt-4">
              <RubberStamp tone="ink" rotate={-3}>
                Verified &middot; every claim checked
              </RubberStamp>
            </div>
          </article>
          <article className="border-2 border-ink bg-paper-raised p-5 shadow-[var(--block-1)]">
            <h3 className="font-head text-xl">If we&rsquo;re in doubt, it&rsquo;s dropped</h3>
            <p className="mt-2 text-sm text-ink-soft">
              A missing story is fine. A wrong one is not. On a quiet day you get a short note, not
              filler.
            </p>
            <div className="mt-4">
              <RubberStamp rotate={3}>Dropped if unsure</RubberStamp>
            </div>
          </article>
        </div>
      </section>

      {/* Weekend and PDF */}
      <section className="defer-render mx-auto max-w-[1200px] px-4 pb-16 sm:px-6">
        <div className="grid gap-6 md:grid-cols-2">
          <article className="relative border-2 border-ink bg-paper-raised p-6 shadow-[var(--block-1)]">
            <div className="absolute -top-3 end-4">
              <RubberStamp rotate={-3}>Extra! Weekend</RubberStamp>
            </div>
            <h3 className="font-head text-xl">Weekend editions</h3>
            <p className="mt-2 text-ink-soft">
              Saturday adds longer reads on the week&rsquo;s biggest stories. Sunday adds a weekly
              recap of what we published. Each comes with a short quiz.
            </p>
          </article>
          <article className="border-2 border-ink bg-paper-raised p-6 shadow-[var(--block-1)]">
            <h3 className="font-head text-xl">An A4 PDF, if you like paper</h3>
            <p className="mt-2 text-ink-soft">
              Every edition has a print-ready PDF, one or two pages for each genre you chose.
            </p>
          </article>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="defer-render border-t border-ink bg-paper-sunk">
        <div className="mx-auto max-w-3xl px-4 py-16 sm:px-6">
          <SectionHeading kicker="Questions">Before you subscribe</SectionHeading>
          <div className="border-t border-dotted border-ink">
            {FAQ.map((item) => (
              <details key={item.q} className="group border-b border-dotted border-ink py-3">
                <summary className="font-head flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 text-lg">
                  <span>
                    <span className="font-slab me-2 text-sm text-press-red">Q.</span>
                    {item.q}
                  </span>
                  <span aria-hidden className="font-figures text-2xl group-open:hidden">
                    +
                  </span>
                  <span aria-hidden className="font-figures hidden text-2xl group-open:inline">
                    &minus;
                  </span>
                </summary>
                <p className="mt-2 max-w-[60ch] text-ink-soft">
                  <span className="font-slab me-2 text-sm text-press-red">A.</span>
                  {item.a}
                </p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="defer-render border-y-4 border-ink">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-6 px-4 py-12 sm:px-6">
          <h2 className="font-mast text-[length:var(--fs-h2)] leading-tight">
            Your first edition is one confirmation away.
          </h2>
          <Link href="/subscribe" className={primaryCta}>
            Start my edition
          </Link>
        </div>
      </section>

      <StickyCta targetId="hero" />
    </>
  );
}
