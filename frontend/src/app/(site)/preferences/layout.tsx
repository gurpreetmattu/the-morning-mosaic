import type { Metadata } from "next";

// Private pages: a title for the tab, and kept out of search results.
export const metadata: Metadata = {
  title: "Manage your subscription",
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
