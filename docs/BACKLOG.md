# Backlog

Running list of what is pending, what is provisional, and what is known to be
broken. Kept in the repo so it survives between sessions.

**Convention:** update this file at the end of every step, in the same commit
as the work. Move finished items to "Done" with the commit that closed them.
Add anything discovered mid-task rather than leaving it in a chat message.

- **Last updated:** 2026-09-17, at commit `4ae281e`
- **State:** 57 commits · 76 backend modules, 22 frontend files, 15 Terraform files, 2 Dockerfiles ·
  473 backend tests, 8 frontend tests (all green, database included) · ruff, `mypy --strict`,
  eslint, prettier, tsc, and `terraform validate`/`fmt` all clean

---

## 1. Blockers — need a decision or an account from the owner

- [ ] **Source terms review.** All 27 sources in `config/sources.yaml` ship
      disabled, so the Collector returns nothing on real config. Each outlet
      needs its terms-of-use and robots.txt checked before `enabled: true`.
      This is a legal judgement, not a code change. *Biggest blocker.*
- [ ] **LLM gateway is unreachable from production.** `freellmpool` serves
      `127.0.0.1:8080`; Cloud Run jobs cannot reach localhost. Decide: deploy
      the gateway as its own Cloud Run service with provider keys in Secret
      Manager, or call providers directly. An architecture gap, not config.
- [ ] **No `.env` and no credentials** for any provider.
- [ ] **External accounts:** Neon, GCP project (`asia-south1`), Gmail app
      password, OpenWeatherMap, market data API, sports API with cricket
      coverage, TMDB, Unsplash/Pexels, Cloudflare Turnstile, Langfuse.
      Longest lead time of anything on this list.
- [ ] **No git remote.** Nothing is pushed anywhere.
- [ ] **CLAUDE.md's agent table and the Orchestrator disagree.** The table
      lists agent 1 as "Yes + code" (uses an LLM), but every responsibility it
      names — supervising, routing retries, enforcing deadlines, applying the
      calendar — is control flow, and `app/agents/orchestrator.py` is built
      with no LLM call. Routing a build through a model would make it
      non-reproducible and would make deadline enforcement depend on a call
      that can itself hang. CLAUDE.md says "keep this honest in docs", so
      either the table moves agent 1 to the code-only list, or there is an LLM
      role here that has not been described. Owner's call; not changed
      unilaterally.

## 2. Defects and gaps in code that already exists

- [ ] **A build before `launch_date` crashes instead of failing cleanly.**
      `edition_number` raises so the day is never numbered zero, which is
      right, but the exception escapes `run_build` as a traceback rather than
      a recorded failed run. Only reachable while `launch_date` is in the
      future — which it is today.
- [ ] **Integration tests share a database with manual runs.** Tests roll back
      their own transactions, but a real `python -m app.jobs.build` commits,
      and one already left a `pipeline_runs` row that broke two tests asserting
      a table held exactly one row. Those assertions are now scoped, but the
      next "count the rows" test will hit it again. A dedicated test database,
      or a truncate fixture, is the real fix.
- [ ] **No admin alerting.** CLAUDE.md wants Cloud Monitoring notifications on
      build failure, deadline miss, send failures and sharp drops in verified
      story counts. The build job records everything needed in `pipeline_runs`,
      and `GET /admin/api/runs` now makes it visible to someone who checks —
      but nothing pushes to anyone, which is what "alert" actually means. That
      still needs a GCP project (see Blockers).
- [ ] **No structured logging.** `structlog` is a dependency but unused; the
      seed job prints. CLAUDE.md requires JSON logs to Cloud Logging. Worth
      doing before more agents land, since each will want it.
- [ ] **No Langfuse tracing** wired, though it is a dependency and in the spec.
- [ ] **No crawl throttling or `Crawl-delay` support.** `RobotsPolicy` honours
      allow/disallow and caches per run, but nothing rate-limits requests to a
      single host. With feeds enabled this could hammer a publisher.
- [ ] **`Fetcher` retry/backoff is not directly tested.** Exercised indirectly
      by the collector tests, never asserted.
- [ ] **Ranker cannot ask the Collector for more coverage.** CLAUDE.md gives it
      that ability ("may ask the Collector for more coverage, whitelisted
      sources only"); it is not implemented. Matters most for strict genres,
      where a story dropped for thin sourcing might be rescued by looking
      wider before giving up on it.
- [ ] **A copied sentence is dropped mid-summary, which can leave the prose
      disjointed.** Verified against a live model, the Writer produced a
      17-word copy in one summary sentence; the check removed that sentence
      and kept the rest. The problem is recorded, so when the Orchestrator
      exists it must treat `copied_text` as retry-worthy *even when a story
      was returned*, rather than publishing the gap.
- [ ] **Acronyms shorter than four characters are not name-checked.** The
      deterministic name check skips candidates under four characters, so an
      invented "SBI" or "IMF" would pass to the model check alone. Raising the
      floor would flood it with false positives; a known-acronym list is the
      likely fix.
- [ ] **Planted-error catch rate is measured by hand, not by an eval.** A live
      run caught 6 of 6 planted errors (wrong figure, wrong day, wrong person,
      invented fact, reversed meaning, unstated causation) with the control
      passing. That belongs in `/evals` as a regression test, not in a
      scratchpad script.
- [ ] **Entity tags accept generic noun phrases.** The check is only that the
      tag appears in the passages, so "central bank" and "two Mumbai
      brokerages" pass alongside "Reserve Bank of India". Harmless for
      grounding, noisy for keyword matching; may want a proper-noun heuristic.
- [ ] **Conflicting key facts are not detected.** The rule is "state that
      reports differ, or drop". Nothing compares figures or claims across the
      articles in a cluster yet. Probably belongs with the Fact-checker, but it
      has no owner today.
- [ ] **Syndication is not detected.** "Independent sources" counts distinct
      source keys, so two outlets running lightly rewritten wire copy count as
      two. Identical text is caught by the Collector's content hash; a rewrite
      is not. Treat the corroboration count as an upper bound.
- [ ] **Neon-specific engine settings untested against Neon.** `pool_pre_ping`
      and `prepare_threshold=None` were reasoned from PgBouncer behaviour and
      have only run against local PostgreSQL.
- [ ] **Seed job requires every env var** just to read `DATABASE_URL`. Fine in
      Cloud Run, friction in dev. Undecided whether to loosen.
- [x] ~~`app/config/loader.py` finds `/config` by walking up from its own
      file, which only lands on the repo root in an editable dev
      checkout.~~ Confirmed by actually building and running the backend
      image: installed into site-packages, the same walk lands inside
      `.venv/lib/python3.12/`, not the repo. Fixed with the existing
      `CONFIG_DIR` override — `backend/Dockerfile` sets it to `/app/config`
      and copies `/config` there — rather than changing the loader, since
      the override already existed for exactly this.
- [ ] **`premailer` is an unused dependency.** Sections are written with inline
      styles directly, so nothing inlines a stylesheet. Either the full email
      template will need it, or it should be dropped.
- [ ] **Section HTML has never been seen in a real mail client.** It is built
      to the email-safe rules (inline styles, no classes, no flexbox) and tests
      assert those, but CLAUDE.md requires checking Gmail web and mobile plus
      Outlook. Nothing has been sent anywhere.
- [ ] **Rate limiting is per process, not per deployment.** `RateLimiter` keeps
      its windows in memory, so with N Cloud Run instances the real signup
      limit is 5 × N per five minutes. Enough to blunt a script, useless
      against a distributed flood. A shared counter (Redis, or a database
      table) is the honest fix if abuse ever appears.
- [ ] **Turnstile has never been exercised against Cloudflare.** Without a
      secret configured the check is skipped outside prod and raises in prod,
      and the verify call itself is covered only by its own error paths. It
      needs one real token round trip once the account exists.
- [ ] **CSRF uses double-submit cookies, not a server-side store.** A
      non-HttpOnly cookie and a request header must match; there is no per-
      session secret, so an attacker who can set cookies on this origin at
      all (e.g. through a subdomain takeover) could satisfy both sides. Fine
      for a single-domain deployment with no subdomains in play; worth
      revisiting if that ever changes.
- [ ] **A session cookie cannot be revoked before it expires.** It is a
      30-day stateless signed token, like a feedback link, so there is no row
      to delete on logout — logout only clears the browser's copy. A stolen
      cookie stays valid until it expires or the signing key is rotated
      (which invalidates every token in the system, not just sessions).
- [ ] **Preferences PATCH has no server-side idempotency key**, unlike
      signup and the delivery claim. Two identical requests both apply
      cleanly (last write wins), so this is a style gap, not a correctness
      one — flagged in case a retrying frontend ever races itself.
- [ ] **`CURRENT_POLICY_VERSION` is a constant in `routes/public.py`.** Every
      consent row records `2026-09-01`, a policy that has not been written.
      DPDP wants consent tied to the text the reader actually saw, so this has
      to move next to the published policy, not live beside the route.
- [ ] **The archive shows no corrections.** CLAUDE.md requires a corrected
      story to be marked in the archive with the correction shown; the route
      serves the pre-rendered section HTML as published and the `corrections`
      table is never read.
- [ ] **The archive lists at most 60 editions** and has no pagination. Fine
      for two months; a decision by January.
- [ ] **`LLMBUFFET_*` naming lags upstream.** The package was renamed to
      `freellmpool`; settings, `.env.example` and CLAUDE.md still say
      LLMBuffet. Cosmetic, but it spreads with every new reference.
- [ ] **The frontend has no Content-Security-Policy.** `next.config.ts` sets
      `X-Content-Type-Options`, `X-Frame-Options`, and `Referrer-Policy`, but
      a CSP was left out rather than fought into shape around the Turnstile
      script it needs to load from `challenges.cloudflare.com`.
- [ ] **Preferences can edit genres, city, and delivery slot, but not
      frequency, edition preference, or followed keywords**, even though
      `PATCH /api/me` supports all of them. A frontend gap, not a backend
      one.
- [ ] **Turnstile has a real widget now but no real site key to test it
      against.** `TurnstileWidget` renders nothing without
      `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, matching the backend's own "skip
      outside prod" behaviour — so signup works end to end in dev, but the
      actual challenge flow has never run.
- [ ] **Privacy and terms are drafts with bracketed placeholders**
      (`[operator name]`, `[date]`, grievance contact), flagged as such on the
      pages themselves. `CURRENT_POLICY_VERSION` (see above) still names a
      policy text that doesn't really exist yet; writing the real policy and
      wiring the two together is one piece of work, not two.

## 3. Provisional values that will cause harm if forgotten

- [ ] **`launch_date: 2026-10-01`** in `config/editions.yaml` is a placeholder,
      and edition numbering derives from it. *Two weeks away.*
- [ ] **21 lunar festival dates missing** (Diwali, Holi, Eid, …), deliberately
      left blank in `awaiting_dates` rather than guessed.
- [ ] **Model choices are unvalidated hypotheses.** Chosen on verified
      behaviour and latency, not measured quality. CLAUDE.md requires an eval
      run before trusting them. The Fact-checker (`kilo/cohere/north-mini-code`)
      is code-oriented by name and specifically needs checking on prose claims.
- [ ] **87 city coordinates unverified** against OpenWeatherMap geocoding.
- [ ] **Free-tier fragility.** During verification OVH rate-limited into a
      circuit-open state, Pollinations began returning 402, and four ids in the
      gateway's own catalogue 404'd or 401'd. A vanished pinned model stops the
      build rather than degrading it — correct, but it will happen.

## 4. Not built yet

**Agents** (5 of 10 done — Orchestrator, Collector, Ranker, Writer, Fact-checker)
- [ ] Image finder (6) · [ ] Weather (7) · [ ] Delivery (9) · [ ] Feedback (10)
- [~] Layout (8) — sections, per-user selection, full email assembly, and
      PDF pages (genre pages once per revision, merged per reader on first
      download) are done. Still to do: the extras the masthead leaves room
      for (weather box is wired but has no Weather agent feeding it; market
      strip, quiz, quote and "On this day" are not built).

**Pipeline**
- [ ] LangGraph build graph · [ ] late-update graph. The Orchestrator runs the
      per-genre pipeline as plain code today; CLAUDE.md specifies LangGraph.
      Decide whether to wrap it or amend the spec.
- [ ] **Preference decay is per run, not per day.** A day with two runs decays
      twice; a skipped day does not decay at all. Keying the decay to elapsed
      days rather than invocations would be the honest version.
- [ ] **Bounce parsing has never seen a real Gmail DSN.** The parser is built
      to RFC 3464 and tested against synthetic reports; `ImapBounceSource` has
      never spoken to an actual IMAP server. Both need a live check once the
      Gmail app password exists.
- [ ] **Whole-*section* withdrawal has no dedicated endpoint.** CLAUDE.md's
      kill switch covers "a story or section"; only story-level withdrawal
      exists (`POST /admin/api/stories/{id}/withdraw`). Withdrawing every
      story in a section by hand gets the same published result, so this is
      a convenience gap, not a capability one.
- [ ] **"New story" is judged by source URL.** A publisher that reissues the
      same story under a fresh URL will be appended twice by the late update.
      Content-hash comparison across clusters would be the stronger check.
- [ ] **Cross-process delivery concurrency is untested.** The claim uses
      `FOR UPDATE SKIP LOCKED` and commits before SMTP, and the at-most-once
      semantics are covered (sent skipped, `sending` never resent, failed
      retried). But two real processes racing for the same reader has never
      been exercised, because the test suite runs in one transaction.
- [ ] Late update: re-collection of breaking stories and publishing a new
      revision
- [ ] Prompt for the Image finder (`ranker_v1`, `writer_v1` and
      `fact_checker_v1` are written; the Orchestrator needs none)

**Delivery path**
- [x] Link-scanner-safe GET endpoints — opt-in, unsubscribe, feedback and now
      the magic link all follow the GET-renders/POST-acts shape.
- [ ] Jinja templates: full email shell with masthead, special, weekend,
      system notices
- [x] PDF assembly and caching — `LocalObjectStorage` in dev, `GcsObjectStorage`
      behind the same interface for prod (untested against a real bucket)
- [ ] Bounce handling over IMAP

**Services**
- [ ] weather · [ ] markets · [ ] sports · [ ] releases · [ ] deals
- [ ] images · [ ] quotes / "On this day"

**Surfaces**
- [x] FastAPI routes — signup, opt-in, unsubscribe, feedback, the archive,
      magic-link login, preferences, pause/resume, DPDP export/delete, the
      PDF download link, and the admin dashboard's backend are all built.
- [x] Next.js frontend — landing, signup (genre picker, Turnstile), the
      archive, preferences (sign-in, edit, pause/resume, export, delete),
      the admin dashboard, and draft privacy/terms pages. Is the single
      public origin in prod too (`src/proxy.ts`); see `infra/README.md`.
- [x] Terraform in `/infra` and both Dockerfiles — never applied (no GCP
      project yet); see the note below and the Done entry for what was
      actually verified.

**Supporting**
- [ ] Evals in `/evals`
- [ ] GitHub Actions (lint, type-check, tests, eval subset on PRs) — also
      the thing that would build and push the two Docker images; today
      that's a manual `docker build`/`docker push`, documented in
      `infra/README.md`.
- [ ] `docs/`: architecture doc, DPDP incident runbook, operational runbooks
- [ ] **`terraform plan`/`apply` have never run against a real project.**
      No GCP project exists yet (Blockers). `terraform validate` passes;
      `fmt` is clean. Two real bugs were only found by going one step
      further and actually building+running both Docker images the config
      deploys (see the WeasyPrint and `CONFIG_DIR` entries above/below) —
      `plan`/`apply` could still turn up more once real credentials exist.
- [ ] **Monitoring covers two conditions, not the four CLAUDE.md lists.**
      Job-execution failure and api 5xx rate are wired (Cloud Run's own
      built-in metrics); a build's deadline miss and a sharp drop in
      verified story counts are not — both need either structured logging
      or a custom metric exporting something from `pipeline_runs`, neither
      of which exists yet.
- [ ] **`api` is publicly invokable, not restricted to `web`.** The web
      service's own proxy calls it over the public internet without
      minting an identity token, so IAM can't be tightened to
      `web`'s service account alone without adding that — real work, not a
      Terraform flag. Noted directly in `infra/cloud_run_api.tf`.
- [ ] **Cloud Run jobs retry zero times (`max_retries = 0`).** Deliberate —
      several jobs (build, late update) aren't safe to blindly rerun
      mid-failure the way Cloud Run's own retry would — but it means a
      transient failure (a cold dependency, a network blip) gets no
      automatic second attempt either. The admin dashboard's manual rerun
      path is the intended recovery, per CLAUDE.md's build-job description.

## 5. Environment

- [x] ~~WeasyPrint cannot run on this machine~~ It can't, but
      `backend/Dockerfile` installs the GTK/Pango/Cairo libraries it needs,
      and `weasyprint_renderer` was verified for real inside the built
      image: `HTML(string=...).write_pdf()` produces genuine PDF bytes.
      Fixed one real bug in the process — the runtime user's `$HOME` wasn't
      writable, so fontconfig couldn't cache, which the image now sets to
      `/tmp`. Unverified: the actual layout of a real section's HTML
      (tested with a trivial string, not `page_html()`'s real output).
- [ ] **`GcsObjectStorage` has never touched real Cloud Storage.** No GCP
      project exists yet (see Blockers). It mirrors `LocalObjectStorage`'s
      interface exactly, so the PDF route needs no change once a bucket
      does exist; the object-key layout (`pdf/sections/{revision}/{genre}.pdf`,
      `pdf/readers/{revision}/{user}.pdf`) is what the 30-day lifecycle
      rule from CLAUDE.md will need to target.
- Local PostgreSQL for tests: `postgresql://postgres:mosaic@localhost:15432/mosaic`
  (`docker rm -f mosaic-pg` to drop it). Set `TEST_DATABASE_URL` to run the
  database tests; they skip without it.
  Port 15432, not 55432: Windows reserves 55416–55515 for Hyper-V, and Docker
  cannot bind inside a reserved range. Check with
  `netsh interface ipv4 show excludedportrange protocol=tcp` before picking a
  port, since the reserved ranges move between reboots.

---

## Done

- [x] Repo scaffold, `uv` project, config layer with validated YAML — `8aacda4`
- [x] 32-table schema and initial migration — `8aacda4`
- [x] Migration made reversible (enum types dropped on downgrade) — `8b8dd40`
- [x] Database session layer and idempotent seeding from `/config` — `19a54dd`
- [x] LLM client: pinned routing, retry, personal-data guard — `8d25d3c`
- [x] Real model ids verified against the live gateway — `a95c45c`
- [x] Collector: whitelist, freshness, robots, passage extraction — `99c944f`
- [x] Project installed as a real package, so `python -m app.jobs.*` runs
      without `PYTHONPATH` — `1b76915`
- [x] Ranker: LLM clustering, deterministic corroboration gate and scoring,
      versioned prompts — `1c39d4a`
- [x] Writer: cited sentences, copy detection, tag taxonomy, code-computed
      india_relevance, hedging for tier-3 — `5273cc0`
- [x] Fact-checker and the write-and-verify loop: deterministic number/date/
      name checks plus model claim verdicts, retry with specific feedback,
      drop after two retries — `b4e2c01`
- [x] Orchestrator: per-genre pipeline, deadline enforcement, failure
      isolation, quiet-day rule, edition numbering and special editions —
      `9064362`
- [x] Persistence of the audit trail: articles, passages, clusters, stories,
      sentences, citations with frozen excerpts, tags and fact checks —
      `74d3add`
- [x] Genre sections rendered to email-safe HTML and plain text, and edition
      revisions published immutably with their sections — `5bcaabc`
- [x] Email layer: signed stateless tokens, hashed stored tokens, SMTP sender
      with the dev allowlist and one-click unsubscribe — `1db440c`
- [x] Per-user selection and full email assembly: keyword, preference and
      edition-preference ordering, masthead, "Today in 60 seconds", computed
      reading time — `8dbc689`
- [x] Delivery job: at-most-once claim, per-reader assembly, retry of failed
      sends, weekday/weekend frequency, dev-suppression recorded as skipped —
      `801f673`
- [x] Failure-notice job: build-independent templates, held batches expiring
      at noon, one-off paused notice on the third failed day, abort when
      sending itself is down — `58a9982`
- [x] Late-update job: appends new stories without mutating published
      revisions, carries unchanged sections forward byte for byte, publishes
      nothing when the deadline passes — `f032aa0`
- [x] Bounce job: read-only mailbox access, narrowed IMAP search, permanent
      failures only — `79726bd`
- [x] Feedback aggregation: bounded and decaying topic preferences, counted
      exactly once — `f2eb000`. **All six scheduled jobs now exist.**
- [x] Build job: the full pipeline behind one command, single-instance job
      lock, pipeline_runs tracking — `43adec4`. Run end to end against the
      live database: it correctly refused to publish, because no source has
      confirmed terms yet, and recorded the failure with diagnostics.
- [x] Public API: signup with double opt-in and the waitlist cap, the
      link-scanner-safe opt-in/unsubscribe/feedback pair of GET and POST,
      one-click unsubscribe, the archive gated until 09:00 IST, security
      headers and rate limiting — `9ba5a47`
- [x] Account API: magic-link login (double-submit CSRF session cookie),
      preferences (genres, keywords, city, slot, frequency, edition
      preference), pause/resume, and DPDP data export and erasure —
      `3c640b1`
- [x] PDF route: two-tier caching (a genre page renders once per revision;
      a reader's file is a cache-or-assemble concatenation of theirs, via
      `pypdf`), bound to the exact revision a link was issued for so a later
      same-day update cannot change what an old link produces, and an
      `ObjectStorage` protocol (disk in dev, Cloud Storage behind a lazy
      import in prod) — `6345bed`
- [x] Admin dashboard (backend): magic-link login restricted to
      `ADMIN_EMAIL`, its own session cookie and CSRF pair kept fully separate
      from a reader's (distinct cookie names, distinct token purpose, so
      neither can be replayed as the other); reads for recent job runs, stuck
      deliveries, and held notice batches; approve/suppress for a notice
      batch; and the story-withdrawal kill switch, which publishes a new
      revision the same way a late update does — `63b2a10`
- [x] Public `/api/config`: genres and the fixed delivery-slot/frequency/
      edition-preference choices from config, active cities from the
      database — the one place the frontend learns what a valid signup or
      preferences payload looks like — `73ebfd6`
- [x] Next.js frontend: landing, signup (genre picker, Turnstile widget),
      the archive, preferences (magic-link sign-in, edit, pause/resume,
      export, delete), the admin dashboard (runs, stuck deliveries, notice
      approve/suppress, story withdrawal), and draft privacy/terms pages.
      TypeScript strict, ESLint + Prettier, a handful of Vitest unit tests
      for the CSRF cookie-parsing logic. In dev, `next.config.ts` proxies
      `/api/*` and `/admin/api/*` to the backend so the backend's
      same-origin session/CSRF cookies work without a load balancer —
      `d686297`
- [x] Terraform (`/infra`) for everything CLAUDE.md's Deployment section
      names: two Cloud Run services, six Cloud Run jobs, Cloud Scheduler
      triggers at CLAUDE.md's exact times, Secret Manager containers (never
      populated by Terraform — values are set by hand, so no secret ever
      touches state), Artifact Registry, the PDF cache bucket (30-day
      lifecycle), and two Cloud Monitoring alerts. `terraform validate` and
      `fmt` pass; `plan`/`apply` need a real GCP project that doesn't exist
      yet. Redesigned the web/api origin problem along the way: rather than
      a load balancer unifying two Cloud Run URLs under a custom domain
      nobody has bought, `web` became the single public origin outright —
      `frontend/src/proxy.ts` (Next 16 renamed Middleware to Proxy) forwards
      everything FastAPI needs to serve to `BACKEND_ORIGIN`. Also added:
      `backend/Dockerfile` and `frontend/Dockerfile`, both actually built
      and run (not just written) — see the WeasyPrint and `CONFIG_DIR`
      entries above for what that caught, and the multi-container network
      test that exercised the whole chain (browser → web's proxy → api →
      real Postgres, and separately the CSRF-protected write path) end to
      end — `4ae281e`
