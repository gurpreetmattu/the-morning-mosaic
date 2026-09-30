import { Dateline } from "@/components/editorial/Dateline";
import { Masthead } from "@/components/editorial/Masthead";
import { SiteNav } from "@/components/editorial/SiteNav";
import { TAGLINE } from "@/content/brand";

/** Inner pages: compact nameplate, narrow reading column. */
export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header>
        <Dateline width="max-w-3xl" />
        <Masthead tagline={TAGLINE} variant="compact" width="max-w-3xl" />
        <SiteNav />
      </header>
      <main id="main" className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6">
        {children}
      </main>
    </>
  );
}
