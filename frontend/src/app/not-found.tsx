import Link from "next/link";
import { PageFrame } from "@/components/editorial/PageFrame";
import { RubberStamp } from "@/components/editorial/RubberStamp";

export const metadata = { title: "Page not found – The Morning Mosaic" };

export default function NotFound() {
  return (
    <PageFrame>
      <RubberStamp rotate={-4}>Not found</RubberStamp>
      <h1 className="font-mast mt-4 text-[length:var(--fs-display)] leading-[1.05]">
        This page went missing.
      </h1>
      <p className="mt-4 text-lg text-ink-soft">
        Here&rsquo;s the front page, and the latest edition if you&rsquo;d like to see what we do.
      </p>
      <p className="font-gothic mt-6 flex flex-wrap gap-6 font-semibold">
        <Link href="/" className="underline">
          Back to the front page &rarr;
        </Link>
        <Link href="/editions/latest" className="underline">
          Read the latest edition &rarr;
        </Link>
      </p>
    </PageFrame>
  );
}
