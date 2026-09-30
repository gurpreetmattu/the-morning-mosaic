"use client";

import Link from "next/link";
import { useEffect } from "react";
import { PageFrame } from "@/components/editorial/PageFrame";
import { Button } from "@/components/ui";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Logged for the browser console only; nothing personal is on this page.
    console.error(error);
  }, [error]);

  return (
    <PageFrame>
      <h1 className="font-mast text-[length:var(--fs-display)] leading-[1.05]">
        Something went wrong on our side.
      </h1>
      <p className="mt-4 text-lg text-ink-soft">
        Try again. If it keeps happening, check the{" "}
        <Link href="/status" className="underline">
          status page
        </Link>
        . A problem with this website does not normally affect your edition.
      </p>
      <div className="mt-6 flex flex-wrap gap-4">
        <Button onClick={reset}>Try again</Button>
        <Link href="/" className="font-gothic self-center font-semibold underline">
          Back to the front page
        </Link>
      </div>
    </PageFrame>
  );
}
