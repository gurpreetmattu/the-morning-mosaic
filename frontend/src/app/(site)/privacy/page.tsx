import Link from "next/link";
import { Notice, PageTitle } from "@/components/ui";
import { serverGet } from "@/lib/server-api";
import type { SiteConfig } from "@/lib/types";

export const metadata = { title: "Privacy policy" };

const FALLBACK_CONTACT = "gurpreetsinghmattu2002@gmail.com";

export default async function PrivacyPage() {
  const config = await serverGet<SiteConfig>("/api/config");
  const operatorName = config?.policy_operator_name ?? "The Morning Mosaic";
  const version = config?.policy_version ?? "unavailable";
  const contactEmail = config?.policy_contact_email ?? FALLBACK_CONTACT;

  return (
    <article className="max-w-[65ch]">
      <PageTitle>Privacy Policy</PageTitle>
      <Notice kind="info">
        Draft — this wording has not yet had legal review. The facts on this page (who operates this
        service, the version date, and the contact address) are real; the phrasing is not final.
      </Notice>

      <p className="font-typewriter mb-4 text-sm text-ink-soft">
        Last updated: {version}. Applies to {operatorName}.
      </p>

      <h2 className="font-head mt-8 mb-2 text-xl">What we collect</h2>
      <p className="mb-4">
        When you sign up, we collect your name, email address, city, chosen genres, delivery time,
        frequency, optional followed keywords, edition preference, your consent record (timestamp
        and policy version), and confirmation that you are 18 or older. We collect nothing else.
        Reading feedback (thumbs up or down on a story) is linked to your account so we can improve
        what we send you.
      </p>

      <h2 className="font-head mt-8 mb-2 text-xl">How we use it</h2>
      <p className="mb-4">
        Your data drives which stories appear in your edition and when it arrives. We never send
        your name, email, city, or any other personal data to the AI models that write and check our
        stories — personalisation happens entirely in our own code, by selecting and ordering
        stories that were already written and verified. Raw article text we fetch for processing is
        kept for 30 days and then purged; the sentences we publish, their sources, and their
        citations are kept permanently as an audit trail.
      </p>

      <h2 className="font-head mt-8 mb-2 text-xl">Who we share it with</h2>
      <p className="mb-4">
        We use third-party services to operate: an email provider to deliver your newsletter, a
        database host, and a bot-check on signup. None of them receive more of your data than is
        necessary to perform that function, and none may use it for their own purposes.
      </p>

      <h2 className="font-head mt-8 mb-2 text-xl">Your rights</h2>
      <p className="mb-4">
        Under India&rsquo;s Digital Personal Data Protection Act, you can access, export, or delete
        your data at any time from{" "}
        <Link href="/preferences" className="underline">
          your preferences page
        </Link>
        . Deletion removes your personal data immediately; records of deliveries and feedback are
        kept in anonymised form for our own operational history. Every email includes an unsubscribe
        link that takes effect immediately.
      </p>

      <h2 className="font-head mt-8 mb-2 text-xl">Grievances</h2>
      <p className="mb-4">
        For a privacy complaint or grievance, contact the {operatorName} privacy team at{" "}
        <a href={`mailto:${contactEmail}`} className="underline">
          {contactEmail}
        </a>
        . We aim to respond within 30 days.
      </p>

      <h2 className="font-head mt-8 mb-2 text-xl">Changes</h2>
      <p>
        If this policy changes, the version you consented to is recorded against your account, and a
        material change will be reflected here with an updated date.
      </p>
    </article>
  );
}
