import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { serverGetStrict } from "@/lib/server-api";
import type { ArchivedEdition } from "@/lib/types";
import { formatLongDate } from "@/components/editorial/format";
import { Notice, PageTitle } from "@/components/ui";

function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(parsed.getTime()) && parsed.toISOString().startsWith(value);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ date: string }>;
}): Promise<Metadata> {
  const { date } = await params;
  if (!isIsoDate(date)) return { title: "Edition not found" };
  const title = formatLongDate(new Date(`${date}T12:00:00+05:30`));
  return {
    title,
    description: `The ${title} edition of The Morning Mosaic, with every story's sources.`,
  };
}

export default async function ArchiveEditionPage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  // Only a real calendar date is ever put into a backend path.
  if (!isIsoDate(date)) notFound();
  const edition = await serverGetStrict<ArchivedEdition>(`/api/archive/${date}`);

  if (edition === null) {
    notFound();
  }

  return (
    <div>
      <PageTitle>{formatLongDate(new Date(`${edition.edition_date}T12:00:00+05:30`))}</PageTitle>
      <p className="font-typewriter mb-8 text-sm text-ink-soft">
        Edition No. {edition.edition_number} · revision {edition.revision}
        {edition.is_weekend && " · weekend edition"}
      </p>

      {edition.corrections.length > 0 && (
        <div className="mb-8 space-y-2">
          {edition.corrections.map((correction, index) => (
            // Layered alongside the frozen section HTML below, never inside
            // it: published content is never edited.
            <Notice key={index} kind="info">
              <strong>Correction — {correction.story_headline}.</strong> {correction.description}
            </Notice>
          ))}
        </div>
      )}

      {edition.sections.length === 0 && (
        <Notice kind="info">This edition has no published sections.</Notice>
      )}

      {edition.sections.map((section) => (
        // Trusted: this HTML is our own backend's pre-rendered, already-escaped
        // section template (app/render/templates/section.html.j2), the exact
        // bytes every reader of this genre received — never user input.
        <div key={section.genre} dangerouslySetInnerHTML={{ __html: section.html }} />
      ))}
    </div>
  );
}
