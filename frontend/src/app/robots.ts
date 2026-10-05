import type { MetadataRoute } from "next";
import { headers } from "next/headers";

/** The origin this request was made to: the site is served from whatever domain maps to it. */
export async function siteOrigin(): Promise<string | null> {
  const h = await headers();
  const host = h.get("x-forwarded-host") ?? h.get("host");
  if (!host) return null;
  return `${h.get("x-forwarded-proto") ?? "https"}://${host}`;
}

export default async function robots(): Promise<MetadataRoute.Robots> {
  const origin = await siteOrigin();
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Private or action-only paths: the account area, the admin, the API and emailed links.
      disallow: [
        "/admin",
        "/preferences",
        "/api/",
        "/opt-in/",
        "/unsubscribe/",
        "/feedback/",
        "/pdf/",
        "/login/",
      ],
    },
    sitemap: origin ? `${origin}/sitemap.xml` : undefined,
  };
}
