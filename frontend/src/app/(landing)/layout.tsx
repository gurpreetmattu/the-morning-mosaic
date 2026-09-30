import { Dateline } from "@/components/editorial/Dateline";
import { Masthead } from "@/components/editorial/Masthead";
import { SiteNav } from "@/components/editorial/SiteNav";
import { TAGLINE } from "@/content/brand";

/** Landing page: full nameplate with ears, full-width sections. */
export default function LandingLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header>
        <Dateline />
        <Masthead tagline={TAGLINE} />
        <SiteNav width="max-w-[1200px]" />
      </header>
      <main id="main" className="flex-1">
        {children}
      </main>
    </>
  );
}
