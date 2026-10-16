import Link from "next/link";
import { ContactAddress, LegalHeading, LegalReviewNotice } from "@/components/editorial/Legal";
import { PageTitle } from "@/components/ui";
import { getPolicyFacts } from "@/lib/policy";

export const metadata = { title: "Privacy policy" };

export default async function PrivacyPage() {
  const { operatorName, version, contactEmail } = await getPolicyFacts();

  return (
    <article className="max-w-[65ch]">
      <PageTitle>Privacy policy</PageTitle>
      <LegalReviewNotice />

      <p className="font-typewriter mb-4 text-sm text-ink-soft">
        {version ? `Last updated: ${version}. ` : ""}Applies to {operatorName}.
      </p>

      <LegalHeading>What we collect</LegalHeading>
      <p className="mb-4">
        When you sign up, we collect your name, email address, city, chosen genres, delivery time,
        frequency, optional followed keywords, edition preference, your consent record (timestamp
        and policy version), and confirmation that you are 18 or older. We collect nothing else from
        you. Reading feedback (thumbs up or down on a story) is linked to your account so we can
        improve what we send you.
      </p>
      <p className="mb-4">
        Like any website, our hosting records standard request details, such as your IP address and
        the time of the visit, in server logs. We use them to run and secure the service.
      </p>

      <LegalHeading>How we use it</LegalHeading>
      <p className="mb-4">
        Your data drives which stories appear in your edition and when it arrives. We never send
        your name, email, city, or any other personal data to the AI models that write and check our
        stories. Personalisation happens entirely in our own code, by selecting and ordering stories
        that were already written and verified. Raw article text we fetch for processing is kept for
        30 days and then purged; the sentences we publish, their sources, and their citations are
        kept permanently as an audit trail. We do not sell your data, and we do not show
        advertising.
      </p>

      <LegalHeading>Cookies and what we store on your device</LegalHeading>
      <p className="mb-4">We do not use analytics or advertising trackers. What we do store:</p>
      <ul className="mb-4 list-disc space-y-2 ps-6">
        <li>
          <strong>When you sign in</strong> with an emailed link, two cookies: a session cookie that
          keeps you signed in for up to 30 days or until you sign out, and a security cookie that
          protects your changes from forged requests. We set no cookies if you only browse.
        </li>
        <li>
          <strong>Your light or dark choice</strong>, in your browser&rsquo;s local storage, until
          you clear it.
        </li>
        <li>
          <strong>While you fill in the signup form</strong>, your genre, city, time and keyword
          choices, in session storage, so a refresh does not lose them. They are gone when you close
          the tab. Your name and email are never stored this way.
        </li>
        <li>
          The signup bot check is run by Cloudflare and may set its own cookies; see
          Cloudflare&rsquo;s policy for those.
        </li>
      </ul>

      <LegalHeading>Who handles it for us</LegalHeading>
      <p className="mb-4">
        We use these services to operate. Each receives only what it needs for its job:
      </p>
      <ul className="mb-4 list-disc space-y-2 ps-6">
        <li>
          <strong>Google</strong>: Google Cloud hosts the website and keeps the PDF copies of
          editions (in Mumbai), and Gmail sends your emails.
        </li>
        <li>
          <strong>Neon</strong>: our database, where your account details are stored.
        </li>
        <li>
          <strong>Cloudflare Turnstile</strong>: the bot check on signup. It sees your IP address
          and browser details to tell people from bots.
        </li>
        <li>
          <strong>OpenWeatherMap</strong>: weather for your city. It receives the city&rsquo;s
          coordinates only, never who you are.
        </li>
        <li>
          <strong>AI model providers</strong>: they receive article text only, never anything about
          you.
        </li>
      </ul>

      <LegalHeading>Your rights</LegalHeading>
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

      <LegalHeading>Grievances</LegalHeading>
      <p className="mb-4">
        For a privacy complaint or grievance, contact the {operatorName} privacy team:{" "}
        <ContactAddress email={contactEmail} />. We aim to respond within 30 days.
      </p>

      <LegalHeading>Changes</LegalHeading>
      <p>
        If this policy changes, the version you consented to is recorded against your account, and a
        material change will be reflected here with an updated date.
      </p>
    </article>
  );
}
