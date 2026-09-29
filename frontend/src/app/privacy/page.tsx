import { PageTitle } from "@/components/ui";
import { serverGet } from "@/lib/server-api";
import type { SiteConfig } from "@/lib/types";

export const metadata = { title: "Privacy Policy — The Morning Mosaic" };

const FALLBACK_CONTACT = "gurpreetsinghmattu2002@gmail.com";

export default async function PrivacyPage() {
  const config = await serverGet<SiteConfig>("/api/config");
  const operatorName = config?.policy_operator_name ?? "The Morning Mosaic";
  const version = config?.policy_version ?? "unavailable";
  const contactEmail = config?.policy_contact_email ?? FALLBACK_CONTACT;

  return (
    <article className="prose-sm max-w-none">
      <PageTitle>Privacy Policy</PageTitle>

      <p className="mb-4 text-sm text-muted">
        Last updated: {version}. Applies to {operatorName}.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">What we collect</h2>
      <p className="mb-4 text-sm">
        When you sign up, we collect your name, email address, city, chosen genres, delivery time,
        frequency, optional followed keywords, edition preference, your consent record (timestamp
        and policy version), and confirmation that you are 18 or older. We collect nothing else.
        Reading feedback (thumbs up or down on a story) is linked to your account so we can improve
        what we send you.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">How we use it</h2>
      <p className="mb-4 text-sm">
        Your data drives which stories appear in your edition and when it arrives. We never send
        your name, email, city, or any other personal data to the AI models that write and check our
        stories — personalisation happens entirely in our own code, by selecting and ordering
        stories that were already written and verified. Raw article text we fetch for processing is
        kept for 30 days and then purged; the sentences we publish, their sources, and their
        citations are kept permanently as an audit trail.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Who we share it with</h2>
      <p className="mb-4 text-sm">
        We use third-party services to operate: an email provider to deliver your newsletter, a
        database host, and a bot-check on signup. None of them receive more of your data than is
        necessary to perform that function, and none may use it for their own purposes.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Your rights</h2>
      <p className="mb-4 text-sm">
        Under India&rsquo;s Digital Personal Data Protection Act, you can access, export, or delete
        your data at any time from{" "}
        <a href="/preferences" className="text-accent underline">
          your preferences page
        </a>
        . Deletion removes your personal data immediately; records of deliveries and feedback are
        kept in anonymised form for our own operational history. Every email includes an unsubscribe
        link that takes effect immediately.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Grievances</h2>
      <p className="mb-4 text-sm">
        For a privacy complaint or grievance, contact the {operatorName} privacy team at{" "}
        <a href={`mailto:${contactEmail}`} className="text-accent underline">
          {contactEmail}
        </a>
        . We aim to respond within 30 days.
      </p>

      <h2 className="mb-2 mt-6 text-lg font-semibold">Changes</h2>
      <p className="text-sm">
        If this policy changes, the version you consented to is recorded against your account, and a
        material change will be reflected here with an updated date.
      </p>
    </article>
  );
}
