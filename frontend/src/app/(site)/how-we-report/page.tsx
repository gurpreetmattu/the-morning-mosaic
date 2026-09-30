import Link from "next/link";
import { RubberStamp } from "@/components/editorial/RubberStamp";
import { PageTitle } from "@/components/ui";
import { serverGet } from "@/lib/server-api";
import type { SiteConfig } from "@/lib/types";

export const metadata = { title: "How we report – The Morning Mosaic" };

const FALLBACK_CONTACT = "gurpreetsinghmattu2002@gmail.com";

const PIPELINE = [
  ["Collect", "We fetch articles from a fixed list of publisher feeds and news services."],
  ["Cluster", "Articles about the same event are grouped, so one story is not told twice."],
  ["Rank", "Stories are scored and checked for corroboration before anything is written."],
  ["Summarise", "The AI rewrites the source text in its own words. It may not add facts."],
  ["Cite", "Every sentence lists the exact passages it came from."],
  [
    "Verify",
    "A second pass checks each claim against those passages. Code checks numbers, dates and names.",
  ],
  ["Publish or drop", "A story that fails after two rewrites is dropped."],
] as const;

function H2({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="font-head mt-12 mb-3 border-t-4 border-double border-ink pt-3 text-[length:var(--fs-h2)] leading-tight">
      {children}
    </h2>
  );
}

export default async function HowWeReportPage() {
  const config = await serverGet<SiteConfig>("/api/config");
  const contact = config?.policy_contact_email ?? FALLBACK_CONTACT;

  return (
    <article className="max-w-[65ch]">
      <PageTitle>How we report</PageTitle>
      <p className="mb-4 text-lg first-letter:font-mast first-letter:float-left first-letter:me-2 first-letter:text-6xl first-letter:leading-[0.8] first-letter:text-press-red">
        Every story in The Morning Mosaic comes from a source we fetched, and every sentence can be
        traced back to it. The AI rewrites; it never supplies facts. This page explains how, and
        where the system can still go wrong.
      </p>

      <H2>Where stories come from</H2>
      <p>
        Only from a fixed, reviewed list of publisher feeds and news services. Each source has a
        credibility tier: wire services, official bodies and primary sources first; established
        outlets second; entertainment outlets third. We respect each site&rsquo;s robots.txt and
        terms, and we skip paywalled pages. Raw article text is used only to write your edition and
        is deleted after 30 days. It is never published.
      </p>

      <H2>How a story is built</H2>
      <ol className="font-gothic mb-4 space-y-3">
        {PIPELINE.map(([name, text], i) => (
          <li key={name} className="flex gap-4 border-b border-dotted border-ink pb-3">
            <span aria-hidden className="font-mast text-3xl leading-none">
              {i + 1}
            </span>
            <span>
              <strong className="block">{name}</strong>
              <span className="text-ink-soft">{text}</span>
            </span>
          </li>
        ))}
      </ol>
      <p>
        India, politics and business stories need at least two independent sources, or one official
        primary source. If sources disagree on a key fact, the story says reports differ, or it is
        dropped. Stories that rest on entertainment outlets alone are worded as reports, not facts.
        Politics is drawn from sources across the spectrum, and stories are worded neutrally, with
        no opinion or loaded adjectives.
      </p>

      <H2>A worked example</H2>
      <p className="mb-3 text-sm text-ink-soft">
        Invented for illustration. This is not a real story or a real publication.
      </p>
      <div className="space-y-3">
        <blockquote className="border-s-4 border-ink bg-paper-raised p-3">
          <p className="kicker mb-1 text-ink-soft">1. Source passage (Example City Gazette)</p>
          <p className="font-typewriter text-sm">
            &ldquo;The council voted 7&ndash;2 on Tuesday to approve a dedicated bus corridor along
            the main ring road.&rdquo;
          </p>
        </blockquote>
        <blockquote className="border-s-4 border-genre bg-paper-raised p-3" data-genre="india">
          <p className="kicker mb-1 text-genre">2. Sentence in your edition</p>
          <p>
            The city council approved a dedicated bus corridor by a 7&ndash;2 vote.
            <sup className="font-figures ms-1 font-bold text-genre">[1]</sup>
          </p>
        </blockquote>
        <p className="text-sm text-ink-soft">
          The checker confirms that the vote and the numbers 7&ndash;2 appear in the cited passage.
          If they did not, the sentence would be sent back to be rewritten.
        </p>
      </div>

      <H2>What we do when we&rsquo;re unsure</H2>
      <p className="mb-4">
        We drop the story. A missing story is acceptable; a wrong one is not. If a genre has fewer
        than two verified stories on a given day, that section carries a short quiet-news-day note
        instead of filler.
      </p>
      <RubberStamp rotate={-3}>Dropped if unsure</RubberStamp>

      <H2>Extras</H2>
      <p>
        Quotes, &ldquo;On this day&rdquo;, market figures, scores and releases come from structured
        data sources, never from the AI. The market strip shows when its data was taken and is not
        investment advice.
      </p>

      <H2>Images and licensing</H2>
      <p>
        Where an image is used, it comes from a source whose licence allows it, and its author,
        source and licence are printed in the edition&rsquo;s credits. We link to publisher images
        rather than copying them. Quotes and &ldquo;On this day&rdquo; entries from Wikipedia and
        Wikiquote are credited under CC BY-SA.
      </p>

      <H2>Corrections</H2>
      <p>
        If a published story turns out to be wrong, it is marked corrected in the archive with the
        correction shown, and a correction note appears in the next edition for readers who received
        it. Published content is otherwise never edited.
      </p>

      <H2>Limits</H2>
      <p>
        This system can still get things wrong. A source can be wrong and the checker will
        faithfully repeat it; the checker can miss a subtle error; and a good story can be dropped
        because it was too hard to verify. Checking a claim against its sources is not the same as
        proving it true. If you spot a mistake, please tell us.
      </p>

      <H2>Contact</H2>
      <p>
        Corrections and questions:{" "}
        <a href={`mailto:${contact}`} className="underline">
          {contact}
        </a>
        .
      </p>

      <p className="mt-10 flex flex-wrap gap-4">
        <Link href="/sample" className="font-gothic font-semibold underline">
          See a sample edition &rarr;
        </Link>
        <Link href="/subscribe" className="font-gothic font-semibold underline">
          Start my edition &rarr;
        </Link>
      </p>
    </article>
  );
}
