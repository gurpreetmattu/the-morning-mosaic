import { Notice, PageTitle } from "@/components/ui";
import { serverGet } from "@/lib/server-api";
import type { SiteConfig } from "@/lib/types";

export const metadata = { title: "Terms of Service — The Morning Mosaic" };

const FALLBACK_CONTACT = "gurpreetsinghmattu2002@gmail.com";

export default async function TermsPage() {
  const config = await serverGet<SiteConfig>("/api/config");
  const operatorName = config?.policy_operator_name ?? "The Morning Mosaic";
  const version = config?.policy_version ?? "unavailable";
  const contactEmail = config?.policy_contact_email ?? FALLBACK_CONTACT;

  return (
    <article className="prose-sm max-w-none">
      <PageTitle>Terms of Service</PageTitle>
      <Notice kind="info">
        Draft — this wording has not yet had legal review. The facts on this page (who operates this
        service, the version date, and the contact address) are real; the phrasing is not final.
      </Notice>

      <p className="mb-4 text-sm text-muted">
        Last updated: {version}. Applies to {operatorName}.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">The service</h2>
      <p className="mb-4 text-sm">
        The Morning Mosaic sends one personalised, newspaper-styled email per subscriber per day,
        assembled from stories verified against fetched, credible sources. This service is available
        only to readers aged 18 and over, based in India.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">No guarantee of delivery</h2>
      <p className="mb-4 text-sm">
        We aim to send every edition on time, but a failed build, an outage, or a technical problem
        can mean a day is missed. When that happens, and it is not the fault of your own mail
        settings, we send a short apology email instead, with no charge either way, as this service
        is offered free of charge.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Corrections</h2>
      <p className="mb-4 text-sm">
        If a published story is later found to be wrong, we mark it corrected in the public archive
        and note the correction in the next edition sent to affected readers. We do not otherwise
        edit what has already been published.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Your account</h2>
      <p className="mb-4 text-sm">
        You may change your preferences, pause delivery, or delete your account at any time from{" "}
        <a href="/preferences" className="text-accent underline">
          your preferences page
        </a>
        . We may suspend or terminate an account used to abuse the signup process or the service.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Content and sources</h2>
      <p className="mb-4 text-sm">
        Every story links to the sources it was drawn from. We do not claim ownership of the
        underlying news; our summaries are original wording produced from those sources, with at
        most a short attributed quotation.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Changes to these terms</h2>
      <p className="text-sm">
        We may update these terms from time to time. Continued use of the service after a change
        takes effect constitutes acceptance of the updated terms.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Contact</h2>
      <p className="text-sm">
        Questions about these terms:{" "}
        <a href={`mailto:${contactEmail}`} className="text-accent underline">
          {contactEmail}
        </a>
        .
      </p>
    </article>
  );
}
