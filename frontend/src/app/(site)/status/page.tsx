import { Notice, PageTitle } from "@/components/ui";
import { serverGet } from "@/lib/server-api";
import type { SiteStatus } from "@/lib/types";

export const metadata = { title: "Status — The Morning Mosaic" };

export default async function StatusPage() {
  const status = await serverGet<SiteStatus>("/api/status");
  const degraded = status?.degraded ?? false;

  return (
    <article>
      <PageTitle>Status</PageTitle>

      {status === null && (
        <Notice kind="error">
          We couldn&rsquo;t load the current status. That doesn&rsquo;t necessarily mean anything is
          wrong — try reloading.
        </Notice>
      )}

      {status !== null && !degraded && (
        <Notice kind="success">All systems operational. Nothing to report right now.</Notice>
      )}

      {status !== null && degraded && (
        <Notice kind="error">
          {status.message ?? "We're aware of an issue and working on it."}
        </Notice>
      )}

      {status?.updated_at && (
        <p className="mt-4 text-sm text-muted">
          Last updated: {new Date(status.updated_at).toLocaleString("en-IN")}.
        </p>
      )}

      <p className="mt-6 text-sm text-muted">
        A missed newsletter, specifically, is never silent: if your edition doesn&rsquo;t arrive on
        a day it should, we send a short apology email instead — this page is for everything else,
        like the website itself being slow or unreachable.
      </p>
    </article>
  );
}
