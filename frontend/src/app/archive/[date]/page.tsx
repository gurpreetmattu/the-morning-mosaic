import { notFound } from "next/navigation";
import { serverGet } from "@/lib/server-api";
import type { ArchivedEdition } from "@/lib/types";
import { Notice, PageTitle } from "@/components/ui";

export default async function ArchiveEditionPage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const edition = await serverGet<ArchivedEdition>(`/api/archive/${date}`);

  if (edition === null) {
    notFound();
  }

  return (
    <div>
      <PageTitle>{edition.edition_date}</PageTitle>
      <p className="mb-8 text-sm text-muted">
        Edition No. {edition.edition_number} · revision {edition.revision}
        {edition.is_weekend && " · weekend edition"}
      </p>

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
