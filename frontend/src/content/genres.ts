// Display data for the ten genres. Blurbs mirror config/genres.yaml (the backend's source).
export type GenreSlug =
  | "india"
  | "politics"
  | "business"
  | "technology"
  | "ai"
  | "sports"
  | "gaming"
  | "bollywood"
  | "hollywood"
  | "music";

export const GENRES: readonly { slug: GenreSlug; name: string; blurb: string }[] = [
  { slug: "india", name: "India", blurb: "The day's most consequential national news." },
  {
    slug: "politics",
    name: "Politics",
    blurb: "Parliament, parties, and policy, reported without a side.",
  },
  { slug: "business", name: "Business", blurb: "Companies, markets, and the economy." },
  {
    slug: "technology",
    name: "Technology",
    blurb: "Products, platforms, and the policy around them.",
  },
  {
    slug: "ai",
    name: "AI",
    blurb: "Models, research, tooling, and the rules being written around them.",
  },
  { slug: "sports", name: "Sports", blurb: "Results, fixtures, and the stories behind them." },
  { slug: "gaming", name: "Gaming", blurb: "Releases, esports, and the business of play." },
  {
    slug: "bollywood",
    name: "Bollywood",
    blurb: "Indian cinema: releases, screens, and the industry.",
  },
  { slug: "hollywood", name: "Hollywood", blurb: "Global film and television." },
  {
    slug: "music",
    name: "Music",
    blurb: "Releases, tours, and the industry behind the charts.",
  },
];

// The genres switched on in config/genres.yaml (`enabled: true`). The landing page is static, so it
// keeps its own copy of that list; backend/tests/test_launch_genres.py fails if the two drift.
export const LIVE_GENRE_SLUGS: readonly GenreSlug[] = [
  "india",
  "business",
  "technology",
  "ai",
  "sports",
];

export const LIVE_GENRES = GENRES.filter((g) => LIVE_GENRE_SLUGS.includes(g.slug));

const NUMBER_WORDS = [
  "zero",
  "one",
  "two",
  "three",
  "four",
  "five",
  "six",
  "seven",
  "eight",
  "nine",
  "ten",
];

/** "five", for copy like "Choose from five." */
export const LIVE_GENRE_COUNT_WORD = NUMBER_WORDS[LIVE_GENRES.length] ?? String(LIVE_GENRES.length);
