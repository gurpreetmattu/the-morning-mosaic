import type { Metadata } from "next";
import Link from "next/link";
import "../styles/fonts";
import "./globals.css";
import { ThemeToggle } from "@/components/editorial/ThemeToggle";
import { BRAND, TAGLINE } from "@/content/brand";

export const metadata: Metadata = {
  title: BRAND,
  description: TAGLINE,
};

// Applies the reader's saved Morning/Late choice before first paint (no flash).
// With no saved choice the CSS follows prefers-color-scheme.
const THEME_INIT = `try{var t=localStorage.getItem("mm-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-IN" className="h-full antialiased" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
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
              &copy; {new Date().getFullYear()} {BRAND}. Set in Abril Fatface, Old Standard TT and
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
              <Link href="/admin" className="hover:underline">
                Admin
              </Link>
              <ThemeToggle />
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
