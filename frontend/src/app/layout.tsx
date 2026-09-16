import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const BRAND = "The Morning Mosaic";
export const TAGLINE = "India's morning, in the pieces that matter.";

export const metadata: Metadata = {
  title: BRAND,
  description: TAGLINE,
};

const NAV_LINKS = [
  { href: "/archive", label: "Archive" },
  { href: "/preferences", label: "Manage subscription" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <header className="border-b border-rule bg-surface">
          <div className="mx-auto flex max-w-3xl flex-wrap items-baseline justify-between gap-x-6 gap-y-2 px-4 py-5 sm:px-6">
            <Link href="/" className="text-2xl font-bold tracking-tight text-foreground">
              {BRAND}
            </Link>
            <nav className="flex gap-5 text-sm">
              {NAV_LINKS.map((link) => (
                <Link key={link.href} href={link.href} className="text-muted hover:text-accent">
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6">{children}</main>

        <footer className="border-t border-rule bg-surface">
          <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 px-4 py-6 text-xs text-muted sm:px-6">
            <p>
              &copy; {new Date().getFullYear()} {BRAND}
            </p>
            <nav className="flex gap-4">
              <Link href="/privacy" className="hover:text-accent">
                Privacy
              </Link>
              <Link href="/terms" className="hover:text-accent">
                Terms
              </Link>
              <Link href="/admin" className="hover:text-accent">
                Admin
              </Link>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
