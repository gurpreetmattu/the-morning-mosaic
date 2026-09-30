import { Dateline } from "@/components/editorial/Dateline";
import { Masthead } from "@/components/editorial/Masthead";
import { SiteNav } from "@/components/editorial/SiteNav";
import { TAGLINE } from "@/content/brand";

/** Subscribe flow: wide enough for the form plus the live "Your edition" panel. */
export default function FlowLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header>
        <Dateline />
        <Masthead tagline={TAGLINE} variant="compact" />
        <SiteNav width="max-w-[1200px]" showSubscribe={false} />
      </header>
      <main id="main" className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-10 sm:px-6">
        {children}
      </main>
    </>
  );
}
