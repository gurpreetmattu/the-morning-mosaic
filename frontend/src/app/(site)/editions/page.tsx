import Link from "next/link";
import { formatLongDate } from "@/components/editorial/format";
import { Lede, Notice, PageTitle } from "@/components/ui";
import { serverGet } from "@/lib/server-api";
import type { ArchivePage } from "@/lib/types";

export const metadata = { title: "Archive" };

// Edition dates are IST calendar dates; noon avoids any day-boundary drift.
const asDate = (isoDate: string) => new Date(`${isoDate}T12:00:00+05:30`);

function monthLabel(isoDate: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    month: "long",
    year: "numeric",
  }).format(asDate(isoDate));
}

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

  const byMonth = new Map<string, NonNullable<typeof editions>>();
  for (const edition of editions ?? []) {
    const label = monthLabel(edition.edition_date);
    byMonth.set(label, [...(byMonth.get(label) ?? []), edition]);
  }

  return (
    <div>
      <PageTitle>Archive</PageTitle>
      <Lede>
        The non-personalised genre sections of each edition, published once the last delivery slot
        (09:00 IST) has passed.
      </Lede>

      {page === null && <Notice kind="error">The archive is unavailable right now.</Notice>}
      {editions !== null && editions.length === 0 && (
        <Notice kind="info">No editions yet. The presses are warming up.</Notice>
      )}

      {[...byMonth.entries()].map(([month, items]) => (
        <section key={month} className="mb-8">
          <h2 className="kicker mb-2 border-b-4 border-double border-ink pb-1">{month}</h2>
          <ul>
            {items.map((edition) => (
              <li key={edition.edition_date} className="border-b border-dotted border-ink">
                <Link
                  href={`/editions/${edition.edition_date}`}
                  className="flex min-h-12 items-baseline gap-3 py-2 hover:bg-paper-sunk"
                >
                  <span className="font-head text-lg">
                    {formatLongDate(asDate(edition.edition_date))}
                  </span>
                  <span
                    aria-hidden
                    className="flex-1 self-end border-b-2 border-dotted border-ink-muted"
                  />
                  <span className="font-typewriter text-sm text-ink-soft">
                    No. {edition.edition_number}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}

      {page?.has_more && oldest && (
        <div className="mt-6">
          <Link
            href={`/editions?before=${oldest}`}
            className="font-gothic text-sm font-semibold underline"
          >
            Older editions &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}
