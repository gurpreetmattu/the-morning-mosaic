import Link from "next/link";
import { Button, Card } from "@/components/ui";
import { TAGLINE } from "./layout";

const GENRES = [
  "India",
  "Politics",
  "Business",
  "Technology",
  "AI",
  "Sports",
  "Gaming",
  "Bollywood",
  "Hollywood",
  "Music",
];

export default function HomePage() {
  return (
    <div>
      <section className="mb-12">
        <h1 className="mb-4 text-4xl font-bold tracking-tight text-balance">{TAGLINE}</h1>
        <p className="mb-6 max-w-xl text-muted">
          One personalised, newspaper-styled email every morning. Pick the genres you care about —
          every story is grounded in a fetched, credible source and traceable back to it. If a day
          is quiet, you get a short note, never a filled-in gap.
        </p>
        <Link href="/signup">
          <Button>Get today&rsquo;s mosaic</Button>
        </Link>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-semibold">Ten genres, one email</h2>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {GENRES.map((genre) => (
            <Card key={genre} className="text-center text-sm font-medium">
              {genre}
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
