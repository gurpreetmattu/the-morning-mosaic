import type { MetadataRoute } from "next";
import { serverGet } from "@/lib/server-api";
import type { ArchivePage } from "@/lib/types";
import { siteOrigin } from "./robots";

const PAGES = ["/", "/subscribe", "/how-we-report", "/editions", "/privacy", "/terms", "/status"];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const origin = await siteOrigin();
  if (!origin) return [];

  const archive = await serverGet<ArchivePage>("/api/archive");
  return [
    ...PAGES.map((path) => ({ url: `${origin}${path}` })),
    ...(archive?.editions ?? []).map((edition) => ({
      url: `${origin}/editions/${edition.edition_date}`,
      lastModified: `${edition.edition_date}T09:00:00+05:30`,
    })),
  ];
}
