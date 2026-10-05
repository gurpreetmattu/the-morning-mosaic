import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { LiveDate } from "@/components/editorial/LiveDate";
import { ThemeToggle } from "@/components/editorial/ThemeToggle";
import { BRAND, TAGLINE } from "@/content/brand";
import { fontVariables } from "../styles/fonts";

export const metadata: Metadata = {
  title: { default: BRAND, template: `%s – ${BRAND}` },
  description: TAGLINE,
  applicationName: BRAND,
  openGraph: {
    type: "website",
    siteName: BRAND,
    title: BRAND,
    description: TAGLINE,
    locale: "en_IN",
  },
  twitter: { card: "summary", title: BRAND, description: TAGLINE },
};

// Runs before first paint. (1) Applies the reader's saved Morning/Late choice, so there is
// no flash; with no saved choice the CSS follows prefers-color-scheme. (2) Marks the first
// landing-page visit of a session, which plays the one-off masthead reveal (DESIGN.md 10).
const HEAD_INIT = `try{var d=document.documentElement,t=localStorage.getItem("mm-theme");if(t==="light"||t==="dark")d.dataset.theme=t}catch(e){}try{if(location.pathname==="/"&&!sessionStorage.getItem("mm-seen")){sessionStorage.setItem("mm-seen","1");document.documentElement.dataset.reveal="1"}}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-IN" className={`${fontVariables} h-full antialiased`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: HEAD_INIT }} />
      </head>
      <body
        className="flex min-h-full flex-col bg-background text-foreground"
        suppressHydrationWarning
      >
        <a href="#main" className="skip-link">
          Skip to content
        </a>

        {children}

        <footer className="border-t-4 border-ink bg-paper-sunk">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-4 py-6 text-sm text-ink-soft sm:px-6">
            <p className="max-w-[60ch]">
              &copy; <LiveDate kind="year" /> {BRAND}. Set in Abril Fatface, Old Standard TT and
              Libre Caslon. Delivered every morning.
            </p>
            <nav aria-label="Footer" className="font-gothic flex flex-wrap items-center gap-4">
              <Link href="/privacy" className="hover:underline">
                Privacy
              </Link>
              <Link href="/terms" className="hover:underline">
                Terms
              </Link>
              <Link href="/status" className="hover:underline">
                Status
              </Link>
              <ThemeToggle />
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
