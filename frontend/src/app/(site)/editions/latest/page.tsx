import { redirect } from "next/navigation";
import { serverGet } from "@/lib/server-api";
import type { ArchivePage } from "@/lib/types";

/**
 * The stable "see what you'll get" link used across the site: the newest
 * published edition, which is real, cited and checked. Before the first
 * edition is published it falls back to the invented layout example at
 * /sample, which labels itself as such.
 */
export default async function LatestEditionPage() {
  const page = await serverGet<ArchivePage>("/api/archive");
  const latest = page?.editions[0]?.edition_date;
  redirect(latest ? `/editions/${latest}` : "/sample");
}
