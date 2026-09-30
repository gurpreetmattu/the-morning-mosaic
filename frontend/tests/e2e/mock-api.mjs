// A tiny stand-in for the FastAPI backend, for browser tests only.
// Serves just the JSON the site reads, from synthetic data (no real articles).
// Signed-in state is a cookie, so a spec can flip it with context.addCookies().
import { readFileSync } from "node:fs";
import { createServer } from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const sectionHtml = readFileSync(join(here, "fixtures", "section-india.html"), "utf8");
const port = Number(process.env.MOCK_API_PORT ?? 8000);

const GENRES = [
  ["india", "India", "The day's most consequential national news."],
  ["politics", "Politics", "Parliament, parties, and policy, reported without a side."],
  ["business", "Business", "Companies, markets, and the economy."],
  ["technology", "Technology", "Products, platforms, and the policy around them."],
  ["ai", "AI", "Models, research, tooling, and the rules being written around them."],
  ["sports", "Sports", "Results, fixtures, and the stories behind them."],
  ["gaming", "Gaming", "Releases, esports, and the business of play."],
  ["bollywood", "Bollywood", "Indian cinema: releases, screens, and the industry."],
  ["hollywood", "Hollywood", "Global film and television."],
  ["music", "Music", "Releases, tours, and the industry behind the charts."],
];
const CITIES = [
  ["mumbai", "Mumbai", "Maharashtra"],
  ["delhi", "Delhi", "Delhi"],
  ["pune", "Pune", "Maharashtra"],
  ["bengaluru", "Bengaluru", "Karnataka"],
  ["chennai", "Chennai", "Tamil Nadu"],
  ["kolkata", "Kolkata", "West Bengal"],
  ["hyderabad", "Hyderabad", "Telangana"],
  ["jaipur", "Jaipur", "Rajasthan"],
];
const SLOTS = ["06:00:00", "06:30:00", "07:00:00", "07:30:00", "08:00:00", "08:30:00", "09:00:00"];

const CONFIG = {
  genres: GENRES.map(([key, display_name, blurb]) => ({ key, display_name, blurb })),
  cities: CITIES.map(([id, name, state]) => ({ id, name, state })),
  delivery_slots: SLOTS,
  frequencies: ["daily", "weekdays"],
  edition_preferences: ["india", "mixed", "global"],
  policy_operator_name: "The Morning Mosaic",
  policy_version: "2026-09-29",
  policy_contact_email: "privacy@example.test",
};

const EDITIONS = [
  { edition_date: "2026-10-02", edition_number: 3 },
  { edition_date: "2026-09-30", edition_number: 2 },
  { edition_date: "2026-09-29", edition_number: 1 },
];

const ME = {
  email: "asha@example.test",
  name: "Asha",
  city_id: "pune",
  status: "active",
  delivery_slot: "07:30:00",
  frequency: "weekdays",
  edition_preference: "india",
  language: "en",
  genres: ["ai", "sports", "music"],
  keywords: ["isro"],
};

function send(res, status, body) {
  const text = JSON.stringify(body);
  res.writeHead(status, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(text),
    Connection: "close",
  });
  res.end(text);
}

createServer((req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost");
  const path = url.pathname;
  const signedIn = (req.headers.cookie ?? "").includes("mm_test_signed_in=1");

  if (req.method === "POST") {
    req.resume();
    return send(res, 200, {
      status: "pending",
      message: "We've sent a link to confirm. Your first edition arrives after you confirm.",
    });
  }
  if (path === "/api/config") return send(res, 200, CONFIG);
  if (path === "/api/status")
    return send(res, 200, { degraded: false, message: null, updated_at: null });
  if (path === "/api/me") {
    return signedIn ? send(res, 200, ME) : send(res, 401, { message: "Not signed in." });
  }
  if (path === "/api/archive") return send(res, 200, { editions: EDITIONS, has_more: false });
  const edition = path.match(/^\/api\/archive\/(\d{4}-\d{2}-\d{2})$/);
  if (edition) {
    const found = EDITIONS.find((e) => e.edition_date === edition[1]);
    if (!found) return send(res, 404, { message: "No such edition." });
    return send(res, 200, {
      ...found,
      revision: 1,
      is_weekend: false,
      corrections: [],
      sections: [{ genre: "india", html: sectionHtml }],
    });
  }
  return send(res, 404, { message: "Not found." });
}).listen(port, "127.0.0.1", () => console.log(`mock api on ${port}`));
