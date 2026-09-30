import Link from "next/link";
import { serverGet } from "@/lib/server-api";
import type { ArchivePage } from "@/lib/types";
import { Card, Lede, Notice, PageTitle } from "@/components/ui";

export default async function ArchiveIndexPage({
  searchParams,
}: {
  searchParams: Promise<{ before?: string }>;
}) {
  const { before } = await searchParams;
  const query = before ? `?before=${encodeURIComponent(before)}` : "";
  const page = await serverGet<ArchivePage>(`/api/archive${query}`);
  const editions = page?.editions ?? null;
  const oldest = editions?.at(-1)?.edition_date;

  return (
    <div>
      <PageTitle>Archive</PageTitle>
      <Lede>
        The non-personalised genre sections of each edition, published once the last delivery slot
        (09:00 IST) has passed.
      </Lede>

      {page === null && <Notice kind="error">The archive is unavailable right now.</Notice>}
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

      {page?.has_more && oldest && (
        <div className="mt-6 text-center">
          <Link href={`/archive?before=${oldest}`} className="text-sm text-accent hover:underline">
            Older editions
          </Link>
        </div>
      )}
    </div>
  );
}
