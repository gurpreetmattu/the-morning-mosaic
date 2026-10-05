import { serverGetRevalidated } from "@/lib/server-api";
import type { LatestHighlights } from "@/lib/types";
import { EditionPreview } from "./EditionPreview";
import { LatestPreview } from "./LatestPreview";

/**
 * The newest real edition when one is published; before the first edition (or
 * if the backend is unreachable) the labelled layout example, so the hero is
 * never empty and never passes invented content off as news.
 */
export async function HeroPreview() {
  const latest = await serverGetRevalidated<LatestHighlights>("/api/latest-edition", 300);
  if (latest && latest.items.length > 0) return <LatestPreview latest={latest} />;
  return <EditionPreview />;
}
