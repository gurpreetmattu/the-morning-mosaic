import Link from "next/link";
import { ContactAddress, LegalHeading, LegalReviewNotice } from "@/components/editorial/Legal";
import { PageTitle } from "@/components/ui";
import { getPolicyFacts } from "@/lib/policy";

export const metadata = { title: "Terms of service" };

export default async function TermsPage() {
  const { operatorName, version, contactEmail } = await getPolicyFacts();

  return (
    <article className="max-w-[65ch]">
      <PageTitle>Terms of service</PageTitle>
      <LegalReviewNotice />

      <p className="font-typewriter mb-4 text-sm text-ink-soft">
        {version ? `Last updated: ${version}. ` : ""}Applies to {operatorName}.
      </p>

      <LegalHeading>The service</LegalHeading>
      <p className="mb-4">
        The Morning Mosaic sends one personalised, newspaper-styled email per subscriber per day,
        assembled from stories verified against fetched, credible sources. This service is available
        only to readers aged 18 and over, based in India.
      </p>

      <LegalHeading>No guarantee of delivery</LegalHeading>
      <p className="mb-4">
        We aim to send every edition on time, but a failed build, an outage, or a technical problem
        can mean a day is missed. When that happens, and it is not the fault of your own mail
        settings, we send a short apology email instead, with no charge either way, as this service
        is offered free of charge.
      </p>

      <LegalHeading>Accuracy</LegalHeading>
      <p className="mb-4">
        Stories are written with the help of AI from the sources they cite, and each claim is
        checked against those sources before it is published. That makes errors unlikely, not
        impossible: a source can be wrong, and a check can miss something. Every story links to its
        sources so you can read them yourself. If you find a mistake, tell us at the address below.
        Market figures in an edition are for information only and are not investment advice.
      </p>

      <LegalHeading>Corrections</LegalHeading>
      <p className="mb-4">
        If a published story is later found to be wrong, we mark it corrected in the public archive
        and note the correction in the next edition sent to affected readers. We do not otherwise
        edit what has already been published.
      </p>

      <LegalHeading>Your account</LegalHeading>
      <p className="mb-4">
        You may change your preferences, pause delivery, or delete your account at any time from{" "}
        <Link href="/preferences" className="underline">
          your preferences page
        </Link>
        . We may suspend or terminate an account used to abuse the signup process or the service.
      </p>

      <LegalHeading>Content and sources</LegalHeading>
      <p className="mb-4">
        Every story links to the sources it was drawn from. We do not claim ownership of the
        underlying news; our summaries are original wording produced from those sources, with at
        most a short attributed quotation.
      </p>

      <LegalHeading>Changes to these terms</LegalHeading>
      <p className="mb-4">
        We may update these terms from time to time. Continued use of the service after a change
        takes effect constitutes acceptance of the updated terms.
      </p>

      <LegalHeading>Contact</LegalHeading>
      <p>
        Questions about these terms, or a mistake to report: <ContactAddress email={contactEmail} />
        .
      </p>
    </article>
  );
}
