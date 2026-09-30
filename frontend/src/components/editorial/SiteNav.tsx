import Link from "next/link";

// Only routes that exist. Sample and How we report join when those pages are built.
const NAV_LINKS = [
  { href: "/archive", label: "Archive" },
  { href: "/preferences", label: "Manage subscription" },
];

export function SiteNav({
  width = "max-w-3xl",
  showSubscribe = true,
}: {
  width?: string;
  showSubscribe?: boolean;
}) {
  return (
    <nav aria-label="Main" className="font-gothic border-b border-rule-soft text-sm font-semibold">
      <div
        className={`mx-auto flex flex-wrap items-center gap-x-6 gap-y-1 px-4 py-2 sm:px-6 ${width}`}
      >
        {NAV_LINKS.map((link) => (
          <Link key={link.href} href={link.href} className="min-h-6 text-ink hover:underline">
            {link.label}
          </Link>
        ))}
        {showSubscribe && (
          <Link
            href="/subscribe"
            className="font-gothic ms-auto border-2 border-ink bg-ink px-3 py-1 text-paper uppercase hover:opacity-90"
          >
            Subscribe
          </Link>
        )}
      </div>
    </nav>
  );
}
