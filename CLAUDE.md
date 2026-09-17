# CLAUDE.md — The Morning Mosaic

## What this project is
The Morning Mosaic is a production-grade, multi-agent AI newsletter. Users pick news genres on
the website, subscribe, and receive one personalized, newspaper-styled email every morning at
their chosen time, with an optional A4 PDF version. This is an end-to-end portfolio project with
real subscribers, not a prototype: build everything to production quality.

**Non-negotiable principle: every factual statement in a newsletter must come from a fetched,
credible source and be traceable to it. The LLM rephrases sources; it never supplies facts.
When in doubt, drop the item. A missing item is acceptable; a wrong one is not.**

This applies to ALL content, including extras (quotes, "On this day", market data, scores,
releases, deals). If an item has no reliable source for the day, omit it.

## Product decisions (already made — ask before changing)
- **Brand / masthead:** "The Morning Mosaic". Masthead is identical across genres: name, tagline,
  date, edition number (sequential count of daily editions since launch; revisions share it),
  "Curated for {first_name}", weather box.
- **Audience:** India only. Users must choose an Indian city (validated list with coordinates).
  All times IST; prices INR; no per-user time zones.
- **Content perspective:** India-first; global stories where natural (AI, Tech, Gaming,
  Hollywood, Music), with an India angle where one exists.
- **Genres (10):** india, politics, business, technology, ai, sports, gaming, bollywood,
  hollywood (global entertainment), music.
- **Stories per genre:** up to 6 verified stories, target 4–6 (1–2 A4 pages). Keyword-matched
  stories replace lower-ranked ones within that cap. If fewer than 2 verified stories exist, the
  section shows a short "quiet news day" note instead.
- **Format:** ONE email per user per day containing all their genres, each as its own themed
  section. Multipart email (responsive HTML + plain text) with a "Download PDF" link.
  The PDF is A4, 1–2 pages per selected genre.
- **Themes:** one fixed theme per genre. Variety comes from special editions (driven only by the
  calendar in `config/editions.yaml`; Indian festival dates change yearly, so the calendar is
  updated each year), a weekend edition, and daily content.
- **Weekend edition:** Saturday = the day's top stories + "longer reads" (extended summaries of
  the week's most significant verified stories) + quiz. Sunday = the day's top stories + weekly
  recap (built from stories already verified and published Mon–Sat) + quiz.
  Users on "weekdays only" frequency receive neither.
- **Newsletter extras:** "Today in 60 seconds", reading time, weather, market strip, "Why this
  matters" on major stories, quote of the day, "On this day", genre extras (scores/fixtures,
  movie/music releases, AI tool of the day, game deals). Each extra has a source in
  "Data sources"; anything without one is not built.
- **Delivery slots:** 30-minute slots from 06:00 to 09:00 IST. Default 07:00.
- **User data collected:** name, email, city, genres, delivery slot, frequency (daily / weekdays),
  optional followed keywords, edition preference (india / global / mixed — adjusts how strongly
  India-relevant stories are ranked), language (English only for now), consent record
  (timestamp + policy version), age confirmation (18+). Nothing else.
- **Subscription states:** pending (awaiting opt-in), active, paused, unsubscribed, bounced,
  waitlisted.
- **Signup:** double opt-in; Cloudflare Turnstile and rate limiting on signup.
- **Accounts:** passwordless magic-link login to manage preferences, pause, and delete account.
- **Archive:** public web archive of the non-personalized genre sections of each edition,
  published after the last delivery slot (09:00 IST).
- **Feedback:** thumbs up/down on each story.
- **Failure notice:** if a subscriber's newsletter will not arrive on a given day, they receive a
  short, generic apology email instead (see "Failure notices").
- **Corrections:** if a published story is found to be wrong, it is marked corrected in the
  archive (with the correction shown) and a correction note appears in the next edition for
  users who received it. Published content is otherwise never edited.

## Architecture

### Jobs (all Cloud Run jobs, triggered by Cloud Scheduler, IST)
1. **Raw-text purge** — 03:00 daily. Clears `Article.raw_text` for articles fetched more than
   30 days ago, per the retention rule under "Data sources". Never touches the audit trail:
   published sentences, their citations' frozen excerpts, and source URLs live elsewhere
   (`SentenceCitation`), not in `Article.raw_text`.
2. **Feedback aggregation** — 04:00. Updates per-user topic preferences from new feedback.
3. **Edition build** — 04:15. Genres run in parallel (bounded by LLM rate limits). Produces, per
   genre, a *verified story pool* (up to 10 stories) with a one-liner and topic tags per story,
   plus section HTML and PDF pages pre-rendered with the Layout module. Publishes the day's first
   revision. Hard deadline: 05:30. If it fails, the admin can start a manual rerun until 07:30
   (rerun deadline 08:45, so the last delivery run can still use it).
4. **Late update** — 05:35 (deadline 05:55) and 07:05 (deadline 07:25). Runs only if a revision
   already exists. Re-collects and verifies breaking/developing stories, re-renders affected
   sections, and publishes a new *edition revision*. Published revisions are never mutated.
   A late update that misses its deadline publishes nothing.
5. **Delivery** — every 30 minutes, 06:00–09:00. Sends to users whose slot is due, using the
   latest published revision at the moment the job starts.
6. **Failure notice** — 09:05. Sends the failure notice to affected users (see below).
7. **Bounce processing** — 05:00 daily. Reads bounce messages from the sender inbox and marks
   addresses `bounced` before the day's deliveries.

Only one instance of each job runs at a time. Cloud Scheduler's free tier covers a small number of
jobs; extra scheduler jobs carry a small monthly fee (check current pricing).

`edition_date` is always the IST calendar date.

**No per-user LLM generation.** Personalization = selecting and ordering stories from verified
pools (genre ranking + followed keywords + feedback preferences + edition preference), done in
code. "Today in 60 seconds" is assembled from pre-written one-liners. Followed keywords are
matched in code against story topic/entity tags, only within the user's subscribed genres.

**Story tags:** the Writer outputs, per story, topic tags (chosen only from the fixed taxonomy
in `config/genres.yaml`), entity tags (people, teams, companies, places — each must appear in the
source passages), and an `india_relevance` flag (true only if the sources mention an Indian
entity or place, checked in code). The Fact-checker verifies them. Tags drive keyword matching,
feedback preferences, and edition preference.

**Failure policy**
- A genre fails or misses the deadline → its section is omitted with a short note. If ALL of a
  user's subscribed genres failed, no newsletter is sent to them (no near-empty email) and they
  get the failure notice instead.
- The whole build fails, or no revision exists when a delivery run starts → that run sends
  nothing, the admin is alerted, and due users roll to the next delivery run (latest 09:00).
  After 09:00, the day is skipped and affected users get the failure notice.
- Never send unverified content.
- **Admin kill switch:** the admin can withdraw a story or section at any time; this publishes a
  new revision without it for users not yet sent. Users who already received it are handled by
  the corrections process.
- **Admin alerts** go through Cloud Monitoring notification channels (e.g. email to
  `ADMIN_EMAIL` sent by Google, or a push app), never through the app's own Gmail sender, so
  alerts still arrive when sending is broken.

### Agents
Agents 2–5 run inside two LangGraph graphs for the build and late-update jobs: one graph per
genre's collect/rank/verify pipeline (`app/graph/build_genre.py`), which calls the Writer/
Fact-checker retry loop as its own nested graph (`app/graph/write_and_verify.py`). Agent 1 (the
Orchestrator) supervises the per-genre graph — deciding which genres run, running them in
parallel, isolating one genre's failure from the rest — rather than being a node inside it.
Agent 6 (Image finder) is not built yet. Agents 7–9 run in the delivery job (plain code); the
Layout module (agent 8) is also called by the build and late update to pre-render sections.
Agent 10 runs in the feedback job.

| # | Agent | Uses LLM? | Responsibility |
|---|-------|-----------|----------------|
| 1 | Orchestrator | No | Supervises the graph, routes retries/failures, enforces deadlines, applies special-edition calendar |
| 2 | Collector | No | Fetches whitelisted RSS + news APIs, extracts full text |
| 3 | Ranker | Yes + code | Dedups, clusters same-event articles, scores, builds the story pool; may ask the Collector for more coverage (whitelisted sources only) |
| 4 | Writer | Yes | Headline, summary, one-liner, tags, and "Why this matters" strictly from source passages, with per-sentence citations |
| 5 | Fact-checker | Yes + code | Verifies every claim; returns failures to Writer; drops story after max retries |
| 6 | Image finder | Yes (text only) + code | Finds licensed images; checks relevance from captions/metadata; records credits |
| 7 | Weather | No | Forecast per city (cached per city per day) |
| 8 | Layout | No | Pre-renders genre sections (build/late update); assembles per-user HTML, plain text, and PDFs |
| 9 | Delivery | No | Sends emails, records status, retries |
| 10 | Feedback | No | Aggregates thumbs up/down into per-user topic preferences |

LLM agents: 3, 4, 5, 6. Tool/code agents: 1, 2, 7, 8, 9, 10. Keep this honest in docs.

## Grounding, freshness, and balance rules (enforce in code, not just prompts)
- **Freshness:** daily stories need a reliable `published_at` within 24h before the build
  (IST-normalized); articles without timestamps are dropped. Relative dates ("yesterday") are
  computed in code, never by the model.
- **Sources:** only whitelisted sources in `config/sources.yaml`, each with genre(s) and a
  credibility tier (1 = wire services, official bodies, primary sources; 2 = established outlets;
  3 = entertainment/gossip). Prefer primary sources. Respect robots.txt and site terms; skip
  paywalled content.
- **Corroboration:** for india, politics, business: ≥2 independent tier-1/2 sources, or one
  primary official source. Conflicting key facts → state that reports differ, or drop.
  Tier-3-only stories must use hedged language ("reportedly").
- **Political balance:** politics sources span the spectrum; neutral wording, no opinion or loaded
  adjectives; ranking must not favor a story because of which side it favors.
- **Writer:** input is full extracted text split into passages with IDs. Output is structured
  JSON where every sentence lists supporting passage IDs. No outside knowledge. Original wording;
  at most a short attributed quoted phrase, never copied paragraphs.
- **"Why this matters":** grounded in the sources (stated implications, expert quotes, official
  statements). Omitted if the sources give no such context.
- **Fact-checker:** split output into atomic claims and verify each against cited passages.
  Numbers, dates, and names are ALSO checked deterministically in code. Unsupported claim →
  back to Writer with the specific error. Max 2 retries. If the core headline/summary still
  fails, drop the story; if only an optional element fails ("Why this matters", a tag, the
  one-liner rewrite), drop just that element.
- **Extras:** quiz questions come only from that edition's verified stories and pass the same
  checks. Quotes, "On this day", scores, releases, market data, and deals come from structured
  data sources, never from the model. Market strip shows the data timestamp and a
  "not investment advice" note; on market holidays and weekends it shows the last close with
  its date.
- **Audit trail:** persist every published sentence with source URLs, the cited passage excerpts
  (kept permanently; only uncited raw text is purged), model and provider, prompt version, and
  check results. Every story links to its sources.

## Data sources
Candidate providers below; before using any, confirm its terms allow display in an email
newsletter and record provider + terms link in config.
- News: publisher RSS feeds (primary), news APIs (NewsData.io / GNews / NewsAPI).
- Full-text extraction: trafilatura.
- Weather: OpenWeatherMap.
- Markets: a market data API whose terms permit redistribution.
- Sports scores/fixtures: a sports data API with cricket coverage.
- Movie releases: TMDB API (attribution required). Music releases: official label/platform
  announcements covered by whitelisted sources.
- Game deals: a deals API such as CheapShark, or official store announcements.
- AI tool of the day: picked from tools covered in that day's verified AI stories.
- Quotes / "On this day": Wikiquote / Wikipedia (CC BY-SA — attribution in the credits section).
- Raw article text is stored for internal processing only, never published, and purged after
  30 days (published sentences, cited passage excerpts, and URLs are kept).

## Images
- Default sources: Wikimedia Commons (respect each license), Unsplash and Pexels (follow their API
  guidelines, including Unsplash's hotlinking and download-tracking requirements).
- Publisher images only when the provider's terms allow display, hotlinked with a link to the
  article. Never download and rehost news photos.
- Every image has a stored credit (author, source, license) shown in the edition's credits
  section. If no suitable licensed image exists, use the genre's default artwork.

## Tech stack
- **Languages:** Python 3.12 (`uv`, one `pyproject.toml` at repo root covering `backend/` and
  `evals/`), TypeScript for the frontend.
- **Backend:** FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2 + Alembic.
- **Agents:** LangGraph for the build and late-update graphs.
- **LLM access:** Groq (OpenAI-compatible; a real, publicly reachable endpoint — previously
  the local `freellmpool` aggregator, which only ever served `127.0.0.1` and so was unreachable
  once deployed).
  - All LLM calls go through `backend/app/llm/client.py`.
  - Writer and Fact-checker use pinned models from `config/models.yaml`; others may use failover.
  - The client supports a configured fallback provider (free tiers can change or restrict use).
  - Never send personal data (names, emails, cities, user IDs) to any LLM.
  - Log token usage, latency, and failures per agent per run.
- **Database:** PostgreSQL on Neon (not Cloud SQL), in the nearest available Asia region,
  pooled connections.
- **Frontend:** Next.js (App Router) + Tailwind, as a Cloud Run service.
- **Email:** Jinja2 templates with inlined CSS; Gmail SMTP (port 587, app password) behind
  `backend/app/email/sender.py`, replaceable by Resend/Brevo once the custom domain is approved.
- **PDF:** WeasyPrint. Genre pages rendered once per revision; per-user PDFs assembled on first
  download, cached in Cloud Storage (30-day lifecycle rule), served via signed links through the API.
- **Region:** GCP `asia-south1` (Mumbai) for Cloud Run, Cloud Storage, and Artifact Registry.
- **Deployment:** Cloud Run (services: web, api; jobs: purge, feedback, build, late-update,
  delivery, failure-notice, bounces), Cloud Scheduler, Cloud Monitoring, Secret Manager, Artifact Registry, Cloud Storage. Terraform in `/infra`,
  state in a GCS bucket. Job timeouts set explicitly. Environments: `dev` (local), `prod`.
  **Dev never emails real subscribers:** outside prod, sending is restricted to an allowlist of
  test addresses (or written to a local mail sink).
- **Observability:** structured JSON logs (Cloud Logging), Langfuse for LLM tracing; alerts on
  build failure/deadline miss, send failures, quota nearing limit, and sharp drops in verified
  story counts, a held failure-notice batch, and bounce-processing errors.
- **CI/CD:** GitHub Actions — lint, type-check, tests, and a small eval set on PRs; full evals
  nightly; deploy on merge to main.

## Data model (core tables)
- Users and subscriptions: users (status, slot, frequency, city_id), cities, user_genres,
  followed_keywords, consents, waitlist, user_preferences, tokens (opt-in, magic link,
  unsubscribe).
- Content: sources, articles, story_clusters, stories, story_sentences (with citations),
  story_tags, fact_checks, corrections, story_withdrawals, images (with credits), extras (quotes,
  markets, scores, releases, deals — with source and timestamp), weather_cache.
- Editions and delivery: editions, edition_revisions, edition_sections, deliveries (type
  newsletter / failure_notice / paused_notice; records the `revision_id` sent, used for PDFs and
  corrections), outage_state (consecutive failed days), feedback (unique on user + story).
- Operations: pipeline_runs, llm_calls, notice_batches (held / approved / suppressed / expired).
- Feedback and PDF links use signed stateless tokens instead of stored rows.

## Email and delivery requirements
- One email per recipient (never BCC). Multipart HTML + plain text.
- `List-Unsubscribe` and `List-Unsubscribe-Post` (one-click HTTPS POST). Unsubscribe is immediate.
- **Link-scanner safety:** email security scanners open links automatically. GET requests on
  opt-in, magic-link, unsubscribe, and feedback links must NOT change state; they show a page with
  a confirm button that POSTs (except the RFC 8058 one-click POST).
- **Gmail quota (~500 recipients/day) covers ALL mail** (newsletters, opt-in, magic links).
  Active subscribers are capped by `MAX_ACTIVE_SUBSCRIBERS` (start at 400) to reserve room for
  transactional mail; beyond the cap, new signups are waitlisted.
- **Idempotency and concurrency:** a delivery row (unique on user_id + edition_date + type) is claimed
  with a row lock and marked `sending` before the SMTP call, then `sent` or `failed`. Rows stuck in
  `sending` are not auto-resent (at-most-once) and are flagged for review. Overlapping delivery
  runs must not process the same user.
- Throttle sends; retry failures on later runs with backoff.
- **Bounces:** Gmail SMTP accepts mail even for bad addresses and reports bounces later as emails
  to the sender inbox. The bounce job reads that inbox over IMAP (the app password grants full
  mailbox access, so the code only reads delivery-failure messages and never sends, deletes, or
  reads other mail) and marks addresses `bounced` after a hard bounce.
- The PDF link in each email points to the exact revision that email contained.
- Images hotlinked, not attached. Test rendering on Gmail (web + mobile) and Outlook.

## Failure notices
- **Recipients:** users due today (active, frequency matches the day) whose newsletter delivery
  for today is missing or `failed` because the whole build failed, all their genres failed, or
  their send failed. Users with a row stuck in `sending` are excluded (they may have received it).
  A single failed genre or missing extra does NOT trigger a notice.
- **Timing:** only at 09:05, after the last delivery run.
  At most one notice per user per day (recorded in `deliveries` with type `failure_notice`).
- **Independence:** a fixed Jinja template (HTML + plain text) with no LLM, news data, external
  images, or dependency on the build output. Same headers as newsletters, including
  unsubscribe. Content is generic: apology, no technical details, "no action needed", next
  edition expected at the usual time.
- **Safety check:** if the recipient count exceeds `FAILURE_NOTICE_AUTO_LIMIT` or looks abnormal,
  the job holds the batch, alerts the admin, and waits for approval in the dashboard. A held batch
  expires unsent at 12:00 IST (a late apology is worse than none). The admin can also suppress
  notices for the day.
- **Prolonged outages:** on the 3rd consecutive failed day for a user, send a one-time
  "newsletter paused" message instead of the regular notice, then send no further notices until
  a newsletter is delivered again. This is a system state (`outage_state`), not the user's
  `paused` subscription status; normal delivery resumes automatically.
- **Email system failures** (SMTP/Gmail unavailable): no notice can be sent; alert the admin only.
- **Website downtime** is shown as a status message on the site, not emailed, unless it stops
  the newsletter.
- Templates live in `backend/app/render/templates/system/`.

## Security, privacy, and legal
- India's DPDP Act: consent at signup, privacy policy, terms, data export and deletion on request,
  and a published contact for privacy grievances. Deletion removes personal data and anonymizes
  deliveries/feedback. Service is 18+.
- Minimal personal data; never log emails or names in plain text.
- Admin dashboard: magic-link login restricted to an allowlisted owner email.
- Sessions use secure, HttpOnly, SameSite cookies; state-changing requests are CSRF-protected.
- Tokens are signed, single-purpose, and expiring (unsubscribe tokens do not expire).
- Validate input; rate-limit public endpoints; set CORS and security headers.
- Daily database backups (provider feature); migrations tested before deploy.
- An incident runbook in `docs/` covers data breaches (DPDP requires notifying the Data
  Protection Board and affected users), leaked secrets, and sending wrong content.
- **Public repo hygiene:** no secrets; test fixtures and eval datasets must not contain full
  copyrighted articles — use short excerpts, synthetic articles, or keep them in private storage.

## Evals (`/evals`)
Groundedness (share of claims supported), freshness (story age at send), dedup/clustering
accuracy, fact-checker catch rate on planted errors, tag accuracy, political neutrality checks.
Any prompt or model change requires rerunning evals; regressions block merge.

## Configuration
- All settings via environment variables (pydantic-settings). Never hardcode URLs, sender details,
  or model names. Key variables: `BASE_URL` (currently the Cloud Run `.run.app` URL; later the
  custom domain), `SENDER_EMAIL`, `SENDER_NAME`, `DATABASE_URL`, `LLM_GATEWAY_URL`,
  `ADMIN_EMAIL`, `APP_ENV` (dev/prod), `TEST_EMAIL_ALLOWLIST`, `MAX_ACTIVE_SUBSCRIBERS`,
  `FAILURE_NOTICE_AUTO_LIMIT`, `TIMEZONE=Asia/Kolkata`.
- Secrets (Gmail app password, token signing key, LLM provider keys, news/weather/market/sports
  API keys, Turnstile secret, Langfuse keys) live in Secret Manager (prod) and `.env` (local).
  `.env` is never committed; `.env.example` lists every variable without values.

## Repository layout
```
/frontend            Next.js: landing, genre picker, signup, preferences, archive, admin, legal pages
/backend/app
  /api               FastAPI routes
  /agents            one module per agent
  /graph             LangGraph definitions (build, late update)
  /jobs              Cloud Run job entry points (purge, feedback, build, late_update, delivery,
                     failure_notice, bounces)
  /llm               client wrapper, versioned prompts
  /sources           fetchers, text extraction
  /email             sender, tokens
  /render            Jinja templates (per genre, special, weekend, system notices), PDF rendering
  /models            SQLAlchemy models
  /services          weather, markets, sports, releases, deals, images, quotes
/backend/migrations  Alembic
/backend/tests
/evals               datasets and eval runners
/config              sources.yaml, genres.yaml, models.yaml, editions.yaml, cities.yaml
/infra               Terraform
/docs                architecture, ADRs, runbooks, BACKLOG.md
```

## Coding conventions
- Python: type hints everywhere; `mypy --strict` passes. Lint/format with `ruff`.
- Frontend: TypeScript `strict`, ESLint + Prettier; the frontend only talks to the FastAPI backend,
  never directly to the database.
- Pydantic models for all agent inputs/outputs; agents unit-testable without network access.
- Unit tests use saved fixtures; no live API or LLM calls in unit tests.
- Every external call has timeouts, retries with backoff, and a logged failure path.
- Jobs are safe to rerun.

## Commands
```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format .
uv run mypy backend
uv run alembic -c backend/alembic.ini upgrade head
uv run python -m evals.run
cd frontend && npm install && npm run dev
cd frontend && npm run lint && npm test
cd infra && terraform plan
```
(Update as scripts are added.)

## How to work on this repo (instructions for Claude)
- Plan before implementing anything non-trivial; list files to be changed.
- Work in small, testable steps; write tests alongside code.
- Never weaken grounding, freshness, balance, or source rules to make a test pass or a story appear.
- Do not add dependencies without stating why.
- Ask before changing any "Product decisions" item.
- Keep `docs/` updated when architecture changes; record significant choices as ADRs.
- Keep `docs/BACKLOG.md` current: it is the running list of pending, provisional, and
  known-broken items. Update it at the end of every step, in the same commit as the work,
  and move finished items to its "Done" section with the closing commit. Anything deferred
  or discovered mid-task goes in the file, not only in conversation.
