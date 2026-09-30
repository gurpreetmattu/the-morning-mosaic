import { Dateline } from "./Dateline";
import { Masthead } from "./Masthead";
import { SiteNav } from "./SiteNav";
import { TAGLINE } from "@/content/brand";

/**
 * Header + main for pages that live outside a route group (404, error), where
 * no group layout supplies them. Masthead stays intact, as DESIGN.md 9.13 asks.
 */
export function PageFrame({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header>
        <Dateline width="max-w-3xl" />
        <Masthead tagline={TAGLINE} variant="compact" width="max-w-3xl" />
        <SiteNav />
      </header>
      <main id="main" className="mx-auto w-full max-w-3xl flex-1 px-4 py-16 sm:px-6">
        {children}
      </main>
    </>
  );
}
