import type { ReactNode } from "react";
import { Notice } from "@/components/ui";
import { POLICY_LEGALLY_REVIEWED } from "@/content/legal";

/** Shown on the legal pages until POLICY_LEGALLY_REVIEWED is switched on. */
export function LegalReviewNotice() {
  if (POLICY_LEGALLY_REVIEWED) return null;
  return (
    <Notice kind="info">
      This page describes in plain language how the service works today. It has not yet been
      reviewed by a lawyer. If anything is unclear or you have a concern, write to us at the address
      at the bottom of this page.
    </Notice>
  );
}

export function LegalHeading({ children }: { children: ReactNode }) {
  return <h2 className="font-head mt-8 mb-2 text-xl">{children}</h2>;
}

/** A mailto link, or an honest message when the address could not be loaded. */
export function ContactAddress({ email }: { email: string | null }) {
  if (!email) {
    return (
      <span>
        our contact address could not be loaded just now. Please reload this page in a moment
      </span>
    );
  }
  return (
    <a href={`mailto:${email}`} className="underline">
      {email}
    </a>
  );
}
