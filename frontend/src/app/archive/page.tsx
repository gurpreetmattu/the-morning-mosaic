import Link from "next/link";
import { serverGet } from "@/lib/server-api";
import type { EditionSummary } from "@/lib/types";
import { Card, Lede, Notice, PageTitle } from "@/components/ui";

export default async function ArchiveIndexPage() {
  const editions = await serverGet<EditionSummary[]>("/api/archive");

  return (
    <div>
      <PageTitle>Archive</PageTitle>
      <Lede>
        The non-personalised genre sections of each edition, published once the last delivery slot
        (09:00 IST) has passed.
      </Lede>

      {editions === null && <Notice kind="error">The archive is unavailable right now.</Notice>}
      {editions !== null && editions.length === 0 && (
        <Notice kind="info">No editions have been published yet.</Notice>
      )}

      <ul className="space-y-3">
        {editions?.map((edition) => (
          <li key={edition.edition_date}>
            <Link href={`/archive/${edition.edition_date}`}>
              <Card className="flex items-center justify-between hover:border-accent">
                <span>{edition.edition_date}</span>
                <span className="text-sm text-muted">Edition No. {edition.edition_number}</span>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
