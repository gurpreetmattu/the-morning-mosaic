# Backlog

Running list of what is pending, what is provisional, and what is known to be
broken. Kept in the repo so it survives between sessions.

**Convention:** update this file at the end of every step, in the same commit
as the work. Move finished items to "Done" with the commit that closed them.
Add anything discovered mid-task rather than leaving it in a chat message.

- **Last updated:** 2026-09-29, at commit `8ee6994` (this refresh adds the
  Langfuse-tracing work on top of it — see its own Done entry — and has not
  been committed as its own separate change yet).
- **State:** 129 commits · 95 backend modules, 23 eval modules, 21 frontend
  TS/TSX files, 15 Terraform files, 2 Dockerfiles, 3 GitHub Actions
  workflows, 2 ADRs, an architecture doc, and an incident runbook · **764
  Python tests passing** with `TEST_DATABASE_URL` set (nothing skipped) · 31
  frontend tests (unchanged this round — no frontend work) · `ruff`,
  `mypy --strict` reverified clean this round; `eslint`, `tsc`, `prettier`,
  `terraform fmt`, and `actionlint` unchanged since the last check (no
  frontend or infra files touched) · **10 of 10 agents built**, unchanged ·
  **7 scheduled jobs**, unchanged · **every genre extra CLAUDE.md names now
  has real code behind it AND actually reaches the delivered email** — see
  the critical extras-never-reached-email fix's Done entry · **Langfuse
  tracing now wired and verified against the real, provisioned account** —
  see its own Done entry, the last item in CLAUDE.md's Observability section
  that had no code behind it; two data-rights gaps are recorded rather than
  resolved (Nifty/Sensex/gold, and Cricbuzz's own redistribution terms) ·
  the real Neon database still has the full schema and reference data (87
  cities, 27 sources) — unchanged this round.

---

## 1. Blockers — need a decision or an account from the owner

- [x] ~~Source terms review.~~ 18 of 27 sources reviewed and enabled by the
      owner; the real Collector now returns real articles across all 10
      genres. See the source-terms-review Done entry for what was
      actually decided, and for two real defects the live run underneath
      it surfaced (a source's malformed feed dates, and an unbounded
      cluster size) — neither is "the terms review," but both were found
      only because it was done for real rather than left disabled.
- [x] ~~LLM gateway is unreachable from production.~~ Resolved by switching
      providers rather than deploying `freellmpool` itself — see the
      llm-gateway-groq Done entry.
- [x] ~~No `.env` and no credentials.~~ A real `.env` now exists with most
      of it filled in — see the accounts-provisioned Done entry.
      `TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY` and everything under
      `GCP_*` are still blank (see below).
- [ ] **External accounts still needed:** GCP project (`asia-south1`,
      for Cloud Run/Scheduler/Secret Manager/Storage — nothing is deployed
      anywhere without this) and Cloudflare Turnstile. Neon, Gmail,
      OpenWeatherMap, a market API, a sports API, TMDB, Unsplash, Pexels,
      and Langfuse are done — see the accounts-provisioned Done entry.
- [ ] **No git remote.** Nothing is pushed anywhere.
- [x] ~~CLAUDE.md's agent table and the Orchestrator disagree.~~ Asked the
      owner: correct the table to match the code, not give the Orchestrator
      an LLM role. See the agent-table Done entry.

## 2. Defects and gaps in code that already exists

- [ ] **No admin alerting.** CLAUDE.md wants Cloud Monitoring notifications on
      build failure, deadline miss, send failures and sharp drops in verified
      story counts. The build job records everything needed in `pipeline_runs`,
      and `GET /admin/api/runs` now makes it visible to someone who checks —
      but nothing pushes to anyone, which is what "alert" actually means. That
      still needs a GCP project (see Blockers).
- [x] ~~Planted-error catch rate is measured by hand, not by an eval.~~ Now
      `evals/fact_checker_catch_rate.py`: 10 deterministic cases (control +
      4 error categories, across 2 base stories) pass today at 100%; the
      other 3 categories (invented prose fact, reversed meaning, unstated
      causation) are built and ready but need a live model to actually
      score — see `evals/README.md`.
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
- [ ] **Section HTML has now been sent for real, but not yet visually
      checked in a mail client.** Added the owner's address to
      `TEST_EMAIL_ALLOWLIST` and sent one full multi-genre edition through
      the real path (`EmailRenderer` -> `Sender` -> actual Gmail SMTP, not a
      mock) — `Sender.send()` returned `outcome=sent` with a real
      `Message-ID`. What's still open is CLAUDE.md's actual ask: someone
      looking at it in Gmail web, Gmail mobile, and Outlook to confirm the
      email-safe markup (inline styles, no classes, no flexbox) actually
      renders as intended in each — that has to be a human check, not
      something this can self-verify.
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
- [ ] **Turnstile has a real widget now but no real site key to test it
      against.** `TurnstileWidget` renders nothing without
      `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, matching the backend's own "skip
      outside prod" behaviour — so signup works end to end in dev, but the
      actual challenge flow has never run.
- [x] ~~The frontend has no component or interaction tests.~~ See the
      component-tests Done entry.
- [ ] **No website-downtime status message.** CLAUDE.md wants site
      downtime shown as a status message on the site rather than emailed,
      unless it stops the newsletter. Low priority: there's no monitoring
      system detecting downtime to drive it yet either, so this is a page
      with nothing to trigger it.

## 3. Provisional values that will cause harm if forgotten

- [ ] **`launch_date: 2026-10-01`** in `config/editions.yaml` is still a
      placeholder, and edition numbering derives from it — only set the real
      value when actually going live. *3 days away as of 2026-09-28.* Local
      testing no longer needs to touch this file to get past it: see the
      `EDITION_LAUNCH_DATE_OVERRIDE` entry in Done.
- [ ] **21 lunar festival dates missing** (Diwali, Holi, Eid, …), deliberately
      left blank in `awaiting_dates` rather than guessed.
- [ ] **The pinned Fact-checker model has a measured, real groundedness gap.**
      No longer an unvalidated hypothesis — see the eval-run Done entry below
      for the full measurement. `tag_accuracy` and `clustering` score 1.00
      for real; `groundedness` scores 0.55–0.90 across repeated live runs
      (threshold 0.90), and even the real `write_and_verify` retry path
      (which this isn't a raw score of) correctly drops a non-trivial share
      of stories rather than publish them under-verified. Something —
      Fact-checker prompt tolerance, a targeted retry on a JSON-decode
      failure specifically, or a different pinned model — needs to change;
      which one is a real decision, not made here.
- [ ] **Free-tier fragility.** During verification OVH rate-limited into a
      circuit-open state, Pollinations began returning 402, and four ids in the
      gateway's own catalogue 404'd or 401'd. A vanished pinned model stops the
      build rather than degrading it — correct, but it will happen.

## 4. Not built yet

**Agents — all 10 of 10 now built.** (Orchestrator, Collector, Ranker,
Writer, Fact-checker, Image finder, Weather, Layout, Delivery, Feedback.
This line previously said "5 of 10" and listed Delivery and Feedback as not
done — stale since those two jobs were built; caught by an audit of this
file against the code, not by anyone noticing the count was wrong. Image
finder (6) is the last one closed — see its own Done entry.)
- [x] ~~Layout (8).~~ Sections, per-user selection, full email assembly, and
      PDF pages (genre pages once per revision, merged per reader on first
      download), the weather box (see the weather-agent Done entry), the
      quote-of-the-day/"On this day" box (see the quotes-extras Done
      entry), a market strip scoped to USD/INR only (see the market-strip
      Done entry), movie releases for bollywood/hollywood (see the
      movie-releases Done entry), music releases for the music genre (see
      the music-releases Done entry), scores/fixtures for the sports genre
      (see the sports-scores-fixtures Done entry), and game deals for the
      gaming genre (see the game-deals Done entry) are all done. **Every
      genre extra CLAUDE.md names is now built — this line was the last
      open item in Layout (8).** The only recorded gaps are data-rights
      ones, not missing code: Nifty/Sensex/gold (see the market-strip Done
      entry) and Cricbuzz's own unresolved redistribution terms (see the
      sports-scores-fixtures Done entry). **A "daily quiz" was never part
      of this line — that was a mistake in this file's own previous
      wording, corrected here.** CLAUDE.md's quiz is weekend-only (already
      built, see the weekend-content Done entry).

**Pipeline**
- [x] ~~LangGraph build graph · late-update graph.~~ Asked the owner:
      actually wrap the pipeline in LangGraph, not amend the spec. See the
      langgraph-pipeline Done entry. The late-update graph is the same
      `build_genre` graph — late update already called the same
      `Orchestrator.build()` the build job does; nothing genre-pipeline-
      specific was ever unique to either job.
- [ ] **Bounce parsing has never seen a real Gmail DSN.** The parser is built
      to RFC 3464 and tested against synthetic reports; `ImapBounceSource` has
      never spoken to an actual IMAP server. Both need a live check once the
      Gmail app password exists.
- [ ] Late update: re-collection of breaking stories and publishing a new
      revision
- [ ] **The Image finder never runs during a late update.** It only attempts
      an image at the initial build, attached once to the section's top
      story at that time. A late update that changes a section's stories
      (`render_candidates`) re-renders it with no image, rather than a fresh
      lookup — noted as a scope limit rather than silently left unhandled.
      See the image-finder Done entry.

**Delivery path**
- [x] Link-scanner-safe GET endpoints — opt-in, unsubscribe, feedback and now
      the magic link all follow the GET-renders/POST-acts shape.
- [x] Jinja templates: full email shell with masthead, special, weekend,
      system notices
- [x] ~~The weekend edition has no content behind it, only a flag.~~ See the
      weekend-content Done entry. **Still open, deliberately out of scope for
      that batch:** the archive (`GET /api/archive/{date}`) shows only genre
      sections, not weekend features, and the PDF has no weekend pages —
      CLAUDE.md's Archive and PDF descriptions both talk only in terms of
      genre sections, so extending either was a separate decision rather than
      part of "give the weekend flag some content."
- [x] PDF assembly and caching — `LocalObjectStorage` in dev, `GcsObjectStorage`
      behind the same interface for prod (untested against a real bucket)
- [ ] Bounce handling over IMAP

**Services**
- [x] ~~weather~~ — see the weather-agent Done entry.
- [x] ~~markets~~ — USD/INR only; see the market-strip Done entry.
      Nifty/Sensex/gold remain blocked on a provider with redistribution
      terms that actually permit newsletter use.
- [x] ~~sports (scores/fixtures)~~ — Cricbuzz via RapidAPI; see the
      sports-scores-fixtures Done entry. **Redistribution terms unresolved
      — a real, open gap, not a false one**, see that entry.
- [x] ~~deals (game deals)~~ — CheapShark, keyless; see the game-deals Done
      entry. All ten genres now have every extra CLAUDE.md names.
- [x] ~~releases~~ — movie releases (TMDB, bollywood/hollywood) and music
      releases (derived from verified stories, no API); see the
      movie-releases and music-releases Done entries.
- [x] ~~images~~ — one per genre section (top story only), from Wikimedia
      Commons/Unsplash/Pexels; see the image-finder Done entry.
- [x] ~~quotes / "On this day"~~ — see the quotes-extras Done entry.
- [x] ~~"AI tool of the day" has no code.~~ See the ai-tool-of-the-day Done
      entry.

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
- [x] Evals in `/evals` — see the Done entry and `evals/README.md`. Four of
      six eval categories score for real today; two (groundedness, tag
      accuracy) and half of a third (fact-checker catch rate, clustering)
      are built but need the LLM gateway to actually run.
- [x] GitHub Actions — `ci.yml` (lint, type-check, tests, the eval suite),
      `evals-nightly.yml`, `deploy.yml` (build+push both images, then
      `terraform apply`). See the Done entry: every job's commands were run
      locally exactly as the workflow specifies and pass; nothing has run
      on GitHub's own infrastructure, since there is no git remote for a
      workflow to run in yet.
- [x] `docs/architecture.md` and `docs/runbooks/incident-response.md` — see
      the Done entry. Still open: other operational runbooks (a manual
      build rerun, approving a held notice batch, rotating out of a
      degraded LLM provider) beyond the one incident-response doc.
- [ ] **`terraform plan`/`apply` have never run against a real project.**
      No GCP project exists yet (Blockers). `terraform validate` passes;
      `fmt` is clean. Two real bugs were only found by going one step
      further and actually building+running both Docker images the config
      deploys (see the WeasyPrint and `CONFIG_DIR` entries above/below) —
      `plan`/`apply` could still turn up more once real credentials exist.
- [ ] **`deploy.yml` has never executed, on GitHub or anywhere else.**
      `actionlint` passes on all three workflows, and every command each
      job runs was run locally exactly as written and passes, but a GitHub
      Actions runner is still a different environment than this one, and
      Workload Identity Federation specifically (the `google-github-actions/auth`
      step) can only be exercised against a real GCP project with the pool
      and provider set up — nothing to test it against yet.
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
- [ ] **The PDF route streams bytes through `api` rather than serving a
      signed link**, which is what CLAUDE.md's tech stack section literally
      specifies ("served via signed links through the API"). Deliberate at
      the time — it keeps one code path uniform across `LocalObjectStorage`
      in dev and `GcsObjectStorage` in prod, rather than generating
      cloud-specific signed URLs — but it means every PDF download's
      bandwidth goes through Cloud Run rather than directly from storage.
      Recording it as a spec deviation rather than letting it pass silently.
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
- [x] Evals (`/evals`) for all six categories CLAUDE.md names, split into a
      deterministic tier (always runs) and an LLM-dependent tier (skipped,
      not failed, when `freellmpool` is unreachable — see `llm_probe.py`).
      Real, current scores today: freshness 100%, fact-checker deterministic
      catch rate 100% (10 cases), neutrality 100% (4 cases), title-only
      clustering fallback 80% (a genuine, previously-unmeasured gap — see
      the Defects entry above). Groundedness, tag accuracy, the full
      fact-checker pipeline, and full clustering are built and unit-tested
      but have never scored a live result — moved the "planted-error catch
      rate measured by hand" item from a standing complaint to actual,
      rerunnable code. `uv run python -m evals.run`; 29 new tests under
      `evals/tests/` (added to pytest's testpaths) cover the eval harness
      itself — the deterministic scoring logic, the LLM-reachability probe,
      and the report/exit-code behaviour — independent of live model
      access — `0ca53b9`
- [x] GitHub Actions: `ci.yml` (backend lint/typecheck/pytest with a
      Postgres service container, frontend lint/typecheck/vitest/build,
      `terraform fmt`/`validate`, and the eval suite — all run in parallel
      except evals, which waits on backend for the same Python
      environment), `evals-nightly.yml` (the same suite on a schedule, with
      room to grow once the LLM gateway blocker is resolved), and
      `deploy.yml` (build+push both images, then `terraform apply`, gated
      on a `GCP_PROJECT_ID` repository variable so it's a safe no-op today
      rather than a workflow that fails loudly on every push). All three
      pass `actionlint` cleanly; every command each job runs was executed
      locally with the job's exact environment (including the eval job's
      dummy-secret recipe) and passes — see the Done entry above for evals,
      and the two entries in section 2 for what genuinely can't be verified
      without a GitHub repository and a GCP project — `54f03c8`
- [x] `docs/architecture.md` (system diagram, the daily job schedule, the
      agent pipeline, the grounding-chain data model, reader-facing
      surfaces, infrastructure — all cross-referencing the code and other
      docs rather than restating them) and `docs/runbooks/incident-response.md`
      (data breach, leaked secrets — a full per-secret rotation table
      including the real, verified consequence that rotating
      `TOKEN_SIGNING_KEY` invalidates every unsubscribe link ever sent,
      since it's HMAC-derived from that key — and sending wrong content).
      Also `docs/adr/0002` recording the single-public-origin decision.
      Writing the "wrong content" section surfaced a real gap, now in
      section 2 above: CLAUDE.md's corrections process (mark a story
      corrected in the archive, note it in the next edition) has no code
      behind it at all, not even the archive-display half already on
      record — `a2aecc7`
- [x] A build before `launch_date` now fails cleanly: `run_build` checks
      `Orchestrator.edition_number` before doing any pipeline work and
      records a `FAILED` `PipelineRun` with the real error, instead of
      letting the `ValueError` escape as an unrecorded traceback — new
      test in `test_build_job.py`.
- [x] Structured JSON logging: `app/logging_config.py` wraps stdlib
      `logging` through `structlog`'s `ProcessorFormatter`, to stdout (Cloud
      Logging parses stdout JSON automatically). All six jobs' `main()` and
      the API's `create_app()` now call it instead of
      `logging.basicConfig(stream=sys.stderr)`; every existing
      `logging.getLogger(__name__)` call site is unchanged.
- [x] Per-host crawl throttling: `Fetcher` now enforces a minimum interval
      between requests to the same host (default 1s), and `RobotsPolicy`
      reads a site's declared `Crawl-delay` and raises that floor via
      `Fetcher.set_crawl_delay`. Direct `Fetcher` retry/backoff and
      throttling tests added in `test_fetch.py` (previously only exercised
      indirectly through the collector tests); `test_robots.py` covers the
      crawl-delay wiring.
- [x] `LLMBUFFET_*` → `FREELLMPOOL_*` rename finished everywhere it lagged:
      `Settings` fields, `.env.example`, Terraform variables/secrets/locals,
      all three GitHub Actions workflows, CLAUDE.md, and every test fixture
      — 30 files, one mechanical rename, `terraform fmt` and the full test
      suite both clean afterward.
- [x] Frontend Content-Security-Policy added in `next.config.ts`:
      same-origin by default, Turnstile's `challenges.cloudflare.com`
      allowlisted for `script-src`/`connect-src`/`frame-src` (the reason a
      CSP was skipped before), `'unsafe-eval'` scoped to dev only for React
      Refresh. Verified: `next build` succeeds, `tsc`/`eslint`/vitest all
      clean, and the header renders correctly against a running dev server.
      Not verified in a real browser against a live Turnstile site key —
      that still needs the Cloudflare account (Blockers).
- [x] `llm_calls` logging finally wired in: the build and late-update jobs
      now pre-create and commit a `PipelineRun` row before any LLM call, so
      `DatabaseCallRecorder` — given its id — can write from its own
      independent session (each `record()` opens and commits its own tiny
      transaction) without a foreign-key race against the main job's own,
      still-open transaction. `DatabaseCallRecorder` itself gained a
      `session_factory` seam and its first tests, in `test_llm_recorder.py`
      — it had none before.
- [x] Acronyms shorter than four characters are now name-checked against a
      curated list (`RBI`, `SBI`, `IMF`, `ISRO`, `GST`, `BCCI`, and 30-odd
      others in `app/agents/checking.py`), including at a sentence's start,
      which the existing "drop the leading word" heuristic used to discard
      unconditionally. Fixing this caught a real, previously-silent gap in
      `test_fact_checker.py`'s own fixture: its passage text never actually
      said "RBI", only "Reserve Bank of India" — invisible while every
      short acronym was skipped, now fixed by writing the passage the way
      real wire copy does, with the abbreviation introduced in parentheses.
- [x] Late update now recognises a reissued story by content hash instead
      of source URL (`app/db/persist.py`'s `persist_new_stories`), so a
      publisher that reissues the same story under a fresh URL is no longer
      appended a second time. The Collector already computed this hash for
      every article; nothing new needed computing it, only comparing it.
- [x] Whole-section withdrawal: `POST /admin/api/editions/{edition_date}/sections/{genre}/withdraw`
      withdraws every active story in a section and publishes one new
      revision — the same published result as withdrawing each story by
      hand, in one call instead of one per story. Reuses the existing
      story-withdrawal machinery (`_carry_forward`, `publish_revision`)
      rather than duplicating it; the section itself renders as a genuine
      `quiet_day`, not an empty `ok` section.
- [x] A special edition now shows its real name in the masthead
      (`EditionsConfig.by_key()` resolves `special_edition_key` in
      `app/jobs/delivery.py`, falling back to the raw key only if it no
      longer matches any configured edition), plus its `.note` as a small
      accented banner and `.accent` as that banner's border colour — both
      previously defined in config and never read anywhere.
- [x] Preference decay now keys to elapsed calendar days rather than to
      how many times the feedback job ran: `UserPreference.last_decayed_at`
      (new column, migration `d5f5dc049b56`, upgrade/downgrade verified
      against a real, fresh Postgres) lets `apply_decay` raise `DECAY` to
      the correct power of elapsed IST days, so a same-day manual rerun no
      longer double-decays and a day the job never ran is caught up fully,
      not skipped, on the next run that does happen.
- [x] `premailer` dropped as a dependency — confirmed unused (sections are
      written with inline styles directly; there is no stylesheet to
      inline yet, since the full email shell is still unbuilt) — along
      with its now-unused transitive dependencies. Revisit only once the
      full email template actually needs to inline a stylesheet.
- [x] `GET /api/archive` is paginated: `limit` (capped at 60) and `before`
      (an edition date cursor) replace the flat 60-edition cap, and the
      response now reports `has_more` rather than letting the caller guess
      from a possibly-short page. Filtering by "is this edition public yet"
      moved into the SQL query itself (`_latest_public_date`), rather than
      fetching a page and filtering in Python, which could silently short
      a page by the one edition — today's — that might not be public yet.
      The frontend archive index now reads the new shape and offers an
      "Older editions" link when `has_more` is true.
- [x] A copied sentence is now retry-worthy in `write_and_verify`
      (`app/agents/verification.py`), instead of `validate_draft` silently
      dropping the sentence and the loop handing a story missing it
      straight to the Fact-checker just because `story is not None`. A
      genuine repro test (`test_a_copied_sentence_retries_instead_of_
      publishing_the_gap`) confirms the Fact-checker is never even called
      on the copied draft — the retry happens one step earlier.
- [x] Entity tags now require the shape of a proper noun
      (`looks_like_a_proper_noun` in `app/agents/checking.py`, reusing the
      same capitalised-word-run regex the name check already had), not just
      that the tag appears somewhere in the passages. Caught an existing
      test asserting the opposite of the fix: `test_writer.py` expected
      "union cabinet" (lowercase, generic) to survive as an entity tag
      because it happened to appear verbatim in the fixture passage —
      updated alongside two new tests for the generic-but-grounded and
      proper-noun-and-grounded cases.
- [x] The Alembic migration chain now actually runs against a real
      database as part of the test suite (`test_the_migration_chain_runs_
      against_a_real_database` in `test_migrations.py`): upgrade → downgrade
      → upgrade, in a throwaway database created and dropped on the same
      Postgres server, fully isolated from every other test (which still
      build their schema via `Base.metadata.create_all`). Runs in CI
      automatically — `TEST_DATABASE_URL` is already set there.
- [x] The preferences dashboard now edits frequency, edition preference,
      and followed keywords, matching the signup form's own controls for
      the same three fields — `PATCH /api/me` already supported all of
      them; only the UI was missing. Verified via `tsc`, `eslint`, and
      `next build`; not click-tested in a real browser this session (no
      browser automation connection available).
- [x] **Critical: five of the six scheduled jobs never ran when invoked
      the way Terraform actually invokes them.** `infra/cloud_run_jobs.tf`
      runs each as `python -m app.jobs.<module>`, which only executes code
      inside `if __name__ == "__main__":`. `feedback.py`, `late_update.py`,
      `delivery.py`, `failure_notice.py`, and `bounces.py` were all missing
      that guard — `main()` was defined but never called, so each would
      fire on schedule, exit 0 immediately, and do nothing, silently. Never
      caught because every job's own tests call `main()` directly,
      bypassing the module-as-script path entirely. Found and fixed by
      actually running `python -m app.jobs.<module> --help` for all six —
      only `build.py` and `seed.py` (which already had the guard) printed
      anything. New regression test
      (`test_job_entrypoints.py::test_the_job_module_actually_runs_as_a_
      script`) runs all six as real subprocesses; verified it fails
      without the fix by reverting one file and rerunning it.
- [x] **Raw article text is now purged after 30 days: the 7th scheduled
      job.** `app/jobs/purge.py`, at 03:00 IST, before feedback
      aggregation — the earliest job of the day, so it never races the
      build. Clears `Article.raw_text` and stamps `raw_text_purged_at` for
      articles fetched past the retention window (default 30 days,
      `--older-than-days` overridable); the audit trail is untouched,
      since it lives in `SentenceCitation`'s own frozen excerpts, never in
      `Article.raw_text`. This was explicitly an architecture change (CLAUDE.md's
      Jobs list said "all Cloud Run jobs," numbered 1–6) rather than a drive-by
      fix, so it was raised as a question first; the owner chose a real 7th
      scheduled job over folding it into an existing one. CLAUDE.md,
      `docs/architecture.md`, and every job-count comment in `/infra`
      updated from six jobs to seven. New migration (`424df135328b`) adds
      `'purge'` to the `job_name` enum (`ADD VALUE IF NOT EXISTS`, so a
      partial downgrade/upgrade cycle can't fail on "already exists");
      Terraform gets the new Cloud Run job and its Cloud Scheduler triggers,
      never applied since no GCP project exists yet (Blockers).
- [x] Integration tests no longer share pollutable state with manual runs
      against the same database. `conftest.py`'s `engine` fixture now
      truncates every table once per test session, before any test runs,
      so a `python -m app.jobs.build` (or any other) run against
      `TEST_DATABASE_URL` by hand can no longer leave rows a later
      `count(session, Model) == N` assertion would see. Verified directly,
      outside pytest: committed a `pipeline_runs` row by hand, ran the full
      suite (still green), and confirmed the row was gone afterward.
- [x] The Ranker can now ask the Collector for more coverage, matching
      CLAUDE.md's agent table exactly. When a strict genre's cluster is
      dropped for `INSUFFICIENT_CORROBORATION`, `Ranker.rank()` calls back
      into the Collector once with a doubled article cap (still whitelisted
      sources only, still the same 24-hour freshness window — CLAUDE.md's
      freshness rule is never loosened to rescue a story) and rebuilds the
      pool from the wider result if it actually found more articles.
      `Collector.collect()` gained a per-call `max_articles` override to
      make this possible; `StoryPool.requested_more_coverage` records
      whether it happened. Wired into the real pipeline in
      `build.py:build_orchestrator()`.
- [x] Syndication is now detected: `independent_sources` (`app/agents/ranking.py`)
      no longer counts distinct source keys directly — it groups articles by
      shingle overlap first (`syndication_overlap`, 8-word shingles, same
      specificity principle as the Writer's own copy check) and counts
      distinct *voices*, so two outlets running the same wire report with
      light rewrites now count as one independent source instead of two.
      Two new tests distinguish a real rewrite (counts as one) from two
      outlets independently covering the same event, which necessarily
      share topical vocabulary without being a copy of each other (still
      counts as two). Exposed a latent flaw in the test fixtures'
      shared filler text along the way — every `article()` helper call used
      the same boilerplate padding, which would have made any two test
      articles look syndicated with each other; fixed by making the filler
      source/title-specific.
- [x] The deterministic clustering fallback's pairwise accuracy improved
      from 80% to 90% (measured, `evals/clustering.py`): `title_tokens`
      (`app/agents/ranking.py`) now stems plurals and past tense with a
      deliberately narrow suffix strip before comparing headlines, which
      closed the "budget" pair's gap ("tax" / "taxes" was the only thing
      keeping it under the 0.5 merge threshold). The "corridor" pair still
      doesn't merge — its headlines paraphrase with genuinely different
      words ("approves" / "clears"), which no lexical heuristic can close
      without risking a false merge elsewhere; that remains exactly what
      the LLM clustering step exists to catch. `TITLE_BASELINE_THRESHOLD`
      raised from 0.75 to 0.85 to hold the gain.
- [x] Conflicting key facts are now detected and dropped, in the Ranker
      (`conflicting_facts` in `app/agents/ranking.py`), not the
      Fact-checker — it needs the full set of raw source articles in a
      cluster, which only the Ranker has at that point. Scoped and
      confirmed with the owner first: this can only ever say "these two
      sentences read like the same claim with different figures," never
      resolve which source is right, so it takes CLAUDE.md's "or drop"
      branch rather than the riskier "state that reports differ" one
      (Writer hedging + Fact-checker verifying it happened). Detection:
      sentence pairs from different articles whose non-numeric wording
      overlaps heavily (≥0.6, same technique as `syndication_overlap`) but
      whose numbers share no value. Checked before the corroboration gate
      and regardless of it — a conflict is a reason to drop on its own, not
      something more sourcing could excuse, so it does not interact with
      the Ranker's own "ask for more coverage" retry. Deliberately
      conservative — most real conflicts won't phrase the disagreement in
      near-identical sentences, so this is a floor, not a complete
      solution, same posture as the clustering fallback above. Five new
      tests, including one proving two *different* facts that both happen
      to be numbers (an injury count and a budget figure) are correctly
      left alone.
- [x] **The corrections process CLAUDE.md specifies now exists, end to
      end.** The `Correction` model already existed
      (`app/models/content.py`) with exactly the shape needed
      (`announced_on`, for gating the note to one edition); nothing wrote
      to it, rendered one, or noted one until now.
      - `POST /admin/api/stories/{id}/correct` records it (admin dashboard:
        "Correct a story"); deliberately separate from
        `/withdraw` — a correction doesn't imply the story needs pulling,
        and withdrawal doesn't imply a correction note is owed.
      - The archive (`GET /api/archive/{edition_date}`) now returns
        `corrections: CorrectionSummary[]`, layered alongside the frozen
        per-genre section HTML rather than touching it — "published content
        is otherwise never edited" holds exactly.
      - `app/jobs/delivery.py` gained `pending_corrections` (marks a
        correction announced for `edition_date` the first time any run that
        day sees it, so every slot that day still includes it — not just
        the first), `correction_recipients`, and `correction_note_for`,
        wired into the existing `EmailRenderer.render(corrections=...)`
        parameter and template block, which had been sitting unused since
        the email layer was built. Genre-and-date matching, not
        story-level — there is still no record of which specific stories a
        reader's selection included that day, only that they received an
        edition — so this over-includes rather than risks missing someone,
        the same trade-off the incident runbook already documented as
        acceptable for the manual workaround it now replaces.
      - `docs/runbooks/incident-response.md`'s "story already reached
        readers" case rewritten from a 5-step manual-SQL workaround to the
        actual endpoint.
      - 11 new backend tests (delivery: received/wrong-genre/never-received/
        not-repeated-next-day/later-same-day-slot; archive: shown
        alongside the frozen section, absent when there are none; admin:
        record/list/404/422/doesn't-withdraw) plus a matching "Correct a
        story" form and list on the admin dashboard and a correction notice
        block on the archive edition page. Frontend verified via `tsc`,
        `eslint`, and `next build`; not click-tested in a real browser this
        session (no browser automation connection available).
- [x] Rate limiting is now a real shared counter, not one per process.
      `RateLimiter` (`app/api/security.py`) is backed by a new
      `rate_limit_hits` table (migration `1972f27b165b`, verified
      upgrade/downgrade against a real Postgres): an atomic
      `INSERT ... ON CONFLICT DO UPDATE ... RETURNING` fixed-window upsert,
      keyed by `(bucket, key, window_start)`, so N Cloud Run instances now
      share one count instead of each enforcing the limit on its own — the
      previous 5×N gap is gone. Uses the caller's own request-scoped
      session rather than an independent one (unlike `DatabaseCallRecorder`
      in `app/llm/recorder.py`): every call site is a route's first line,
      and an independent session is exactly what the test suite's
      dependency-injected session can't accommodate without real settings
      behind it — a documented, deliberate trade-off, not an oversight. All
      four limiters (signup, feedback, reader login, admin login) updated
      to pass the request session; the admin-login route gained one, since
      it never needed the database before. `app/jobs/purge.py` also clears
      `rate_limit_hits` rows older than a day, so the table doesn't grow
      forever — every window is a few minutes at most. 10 new tests: 8
      unit tests for the limiter itself (including one directly proving
      two independently constructed `RateLimiter` objects with the same
      name share one count, standing in for two Cloud Run instances), 2
      for the new purge behaviour.
- [x] Cross-process delivery concurrency is now genuinely exercised.
      `test_delivery_concurrency.py` opens two (and separately, six) real
      independent sessions against the actual test database — not the
      shared savepoint-scoped `session` fixture every other test uses,
      which is one connection and so can never race a *second* transaction
      against `claim()`'s `SELECT ... FOR UPDATE SKIP LOCKED` — synchronises
      them with a `threading.Barrier` so they attempt the same claim at the
      same instant, and cleans up everything it commits itself, since the
      usual per-test rollback does not apply to real commits. Writing it
      surfaced a genuine subtlety worth recording, not a bug: `claim()`
      alone does not exclude a second caller from a still-`PENDING` row —
      only `run_delivery`'s immediate `status = SENDING` + commit right
      after `claim()` returns does. The first test written skipped that
      step and got two "successful" claims back, which is correct given
      what the function actually promises, not a false pass — fixed by
      making the test mirror `run_delivery`'s real sequence.
- [x] Weekend edition content: Saturday's "longer reads" and Sunday's
      "weekly recap", plus the weekend quiz — `96eb0f6`. New
      `app/render/weekend.py`, driven by `config/editions.yaml`'s
      `weekend.saturday_features`/`sunday_features` (parsed since the
      initial schema but never read until now — "top-stories" needs no code
      of its own, since it is just that day's ordinary per-genre sections).
      Everything is selected from stories already verified and persisted
      earlier the same week (a story counts as "significant" if it was
      pool-ranked 1–3 in its own genre that day) — no LLM call and nothing
      invented, per CLAUDE.md's "No per-user LLM generation": longer reads
      carry a picked story's own already-checked headline/summary/why-this-
      matters; the recap is the same stories as a compact headline list; the
      quiz is multiple-choice with the real headline as the correct answer
      against decoys that are themselves other stories' real, already-
      checked headlines — nothing is invented, and the grounded answer links
      back to its own source, deterministically shuffled per edition date so
      a rerun produces the same quiz. New `weekend_features` table (one row
      per edition_date + kind, replaced wholesale on a rerun rather than
      versioned — a late update cannot change what earlier in the week
      already said, so there is nothing to re-render). Wired into the build
      job (right after the day's own genre sections persist) and the
      delivery job (loaded once per run, same content for every reader,
      same as "today in 60 seconds"). New email template blocks, HTML and
      plain text. Deliberately **not** extended to the public archive or the
      PDF this batch — see the note left in "Not built yet" — since
      CLAUDE.md's Archive and PDF sections both talk only in terms of genre
      sections, and stretching either was a separate decision from "give the
      weekend flag some content." 30 new tests: pure selection/quiz-shape
      tests, a persist/load round trip against a real database (including
      that a rerun replaces rather than duplicates), a `run_build` test that
      seeds a real preceding week and checks the Saturday build's own
      report, and two `run_delivery` tests (a Saturday email carries the
      block, an ordinary weekday email carries none).
- [x] Frontend component and interaction tests for signup, preferences, and
      the admin dashboard — `59a99f0`. Added the standard Next.js/Vitest
      pieces the project didn't have yet (`jsdom`, `@vitejs/plugin-react`,
      `@testing-library/react` + `/dom` + `/user-event` + `/jest-dom`) —
      `frontend/src/lib/api.test.ts` existed only because it tests plain
      functions in a Node environment, never actually rendering a
      component. `vitest.config.mts` now runs under `jsdom` and uses Vite's
      native `resolve.tsconfigPaths` for the `@/*` import alias rather than
      the `vite-tsconfig-paths` plugin the docs still suggest — the
      installed Vite already warned that its own option supersedes it.
      New `frontend/src/lib/test-fetch.ts`: a tiny router over a mocked
      `fetch` (exact-path or longest-prefix match) so each test states
      what a path returns rather than hand-rolling `Response`-shaped
      objects. 23 new tests across the three pages: config loading and its
      failure notice, both client-side validation messages on signup,
      genre-checkbox toggling, the exact signup payload sent (including
      that a Turnstile-less dev environment omits `turnstile_token`
      entirely rather than sending it as `null`), the waitlisted-vs-pending
      confirmation heading, magic-link sign-in on both reader and admin
      login forms, saving edited preferences, pause/resume, the delete-
      account confirmation step, approving a held notice batch, and
      submitting a withdrawal and a correction with their exact bodies.
      One real race condition surfaced while writing these, not a bug in
      the pages: the admin dashboard's own heading renders before its
      `Promise.all` of five endpoints resolves, so a test that waited only
      for the heading before clicking "Approve" was reading the DOM before
      the button existed — intermittently, not on every run. Fixed by
      waiting on data-dependent content (the loaded run, the notice text)
      instead of the always-present heading; confirmed stable across
      repeated runs once fixed.
- [x] "AI tool of the day" — `dfced8f`. CLAUDE.md's own wording ("picked
      from tools covered in that day's verified AI stories") leaves the
      actual selection open: stories carry untyped entity tags (people,
      companies, places all mixed together), not a "this one names a tool"
      flag, so there was no reliable way to point at a specific tool name
      without inventing a maintained allow-list. Asked the owner how to
      scope it (`AskUserQuestion`) rather than guess; picked the
      recommended option — feature the day's top-ranked verified AI story
      itself as "AI tool of the day," rather than trying to extract a tool
      name from it. Fully deterministic and grounded in exactly the
      headline/one-liner/source every reader already sees in the section
      below, so nothing new is invented.
      Implemented in `app/render/sections.py` rather than as a per-user
      `Extra` row: `ExtraKind.AI_TOOL` already existed on the model but
      nothing ever built or rendered any `Extra`, and CLAUDE.md's "genre
      extras" framing (alongside scores/fixtures, movie/music releases)
      means this belongs in the shared, once-per-revision genre section —
      same place archive readers and every emailed reader both see it from
      — not behind new per-user plumbing. `SectionRenderer.render()` reads
      it straight from the AI genre's already-rank-ordered
      `GenreOutcome.stories`; `render_candidates()` (the late-update path,
      working from persisted rows instead) picks by `pool_rank` for the
      same result. No new table, no migration. New template blocks in
      `section.html.j2`/`.txt.j2`, gated on genre so no other section ever
      shows one. 7 new tests: the callout appears only for the AI genre,
      only for the top-ranked story, falls back to the first summary
      sentence when a story has no one-liner, and is absent on a quiet or
      failed AI day — covering both the fresh-build and the
      render-from-persisted-rows paths.
- [x] CLAUDE.md's agent table now matches the code — `0ae8b62`. Asked the
      owner directly rather than guessing: correct the table, or give the
      Orchestrator a real LLM-backed responsibility? Answer was to correct
      the table. Agent 1 moved to "No" (uses an LLM: No) in the table, and
      the line-133 summary now reads "LLM agents: 3, 4, 5, 6. Tool/code
      agents: 1, 2, 7, 8, 9, 10." `app/agents/orchestrator.py`'s own
      docstring and `docs/architecture.md`'s pipeline diagram note both
      described this exact disagreement as deliberate — updated to say the
      table now matches, rather than leaving a resolved discrepancy
      documented as still open in three different places.
- [x] The build/late-update pipeline actually runs on LangGraph — `a2de574`.
      Asked the owner: amend CLAUDE.md to drop the LangGraph claim, or
      actually build it? Answer was to build it — real, non-trivial work,
      not a doc fix. Two new graphs, matching the two loops
      `docs/architecture.md`'s own diagram already drew:
      `app/graph/build_genre.py` (agents 2-3: one genre's
      collect -> rank -> verify-every-candidate pipeline, replacing
      `Orchestrator.build_genre`'s hand-rolled loop) and
      `app/graph/write_and_verify.py` (agents 4-5: the Writer/Fact-checker
      retry loop, replacing `write_and_verify`'s hand-rolled `for` loop) —
      the first graph's "verify one candidate" step calls the second as an
      ordinary function call, so the retry loop exists in exactly one
      place rather than being duplicated. Agent 1 (the Orchestrator) stays
      outside both graphs, supervising rather than participating, matching
      the agent-table entry above.
      `Orchestrator.build_genre()` and `write_and_verify()` keep their
      exact original signatures and behaviour on purpose: every existing
      test that exercises them (`test_orchestrator.py`'s 17 tests,
      `test_fact_checker.py`'s 4 loop tests, including exact LLM-call-count
      assertions against a mocked gateway) passes unmodified, which is the
      real proof the refactor changed nothing observable. `CollectorLike`/
      `RankerLike`/`VerifyFn`/`QUIET_DAY_NOTE`/`FAILED_NOTE` now live in
      `app/graph/build_genre.py` and are re-exported from
      `app/agents/orchestrator.py` for the existing call sites, rather than
      being defined in both places and risking drift.
      6 new tests: each compiled graph is asserted to actually be a
      LangGraph `CompiledStateGraph`; `build_genre`'s loop is exercised at
      pool_size 20 (`config/schemas.py`'s real ceiling), and
      `write_and_verify`'s loop is exercised at 30 retries and at zero —
      well past CLAUDE.md's mandated 2 — with lightweight fakes rather
      than a mocked LLM, since this is about the loop's own mechanics, not
      grounding. One assumption corrected while investigating: LangGraph's
      default recursion limit in the installed version (1.2.11) is 10007,
      not the 25 an earlier version's docs suggested — an explicit
      `recursion_limit` override was drafted, tested, found unnecessary,
      and removed rather than left in as defensive code against a premise
      that turned out to be false.
- [x] The LLM gateway is a real, publicly reachable endpoint — `7ff92bf`.
      Closes the "LLM gateway is unreachable from production" Blockers
      entry. Considered Alibaba Cloud Model Studio first (owner checked it
      personally): its free tier is a one-time 90-day/1M-token trial per
      model, not ongoing, and only on the Singapore endpoint — confirmed
      against Alibaba's own docs rather than trusting the first search
      result. Compared against several genuinely-ongoing free-tier
      providers (Groq, Cerebras, OpenRouter, Mistral, Google AI Studio);
      owner picked Groq for its higher daily request ceiling and no
      training-data use.
      `Settings.freellmpool_url`/`freellmpool_api_key` renamed to
      `llm_gateway_url`/`llm_gateway_api_key` — CLAUDE.md named
      "freellmpool" specifically as the LLM access layer, and that was no
      longer true once Groq replaced it everywhere (dev and prod both, not
      just behind it), the same reasoning as the agent-table fix. Renamed
      across `Settings`, `.env`/`.env.example`, `infra/*.tf`,
      `infra/terraform.tfvars.example`, all three GitHub Actions
      workflows, CLAUDE.md, `docs/architecture.md`,
      `docs/runbooks/incident-response.md`, `evals/README.md`,
      `evals/llm_probe.py`, and every test fixture that built a `Settings`
      by hand — the same shape of rename `docs/BACKLOG.md` already
      records once before (`LLMBUFFET_*` → `FREELLMPOOL_*`).
      `config/models.yaml` rebuilt against Groq's actual live catalog
      (`GET /openai/v1/models` with the real key), not its published docs:
      the docs-recommended `llama-3.3-70b-versatile` and
      `llama-3.1-8b-instant` both 404 on this account. Verified live,
      end to end through `Writer`/`FactChecker`/`write_and_verify`, not
      just a bare completion: pinned Writer on `openai/gpt-oss-120b`,
      pinned Fact-checker on `qwen/qwen3.8-27b` (deliberately a different
      vendor lineage, per the existing CLAUDE.md rule). One real defect
      surfaced by that live run, unrelated to the gateway swap: a fresh
      `.env` with `TURNSTILE_SECRET_KEY=` (present but blank) made
      `verify_turnstile` treat the secret as configured — pydantic-settings
      resolves a blank env value to `SecretStr("")`, not `None` — so real
      local signups were silently failing Turnstile verification outside
      prod, where CLAUDE.md wants an unconfigured secret to skip the check
      entirely. Fixed in `app/api/security.py` (and the identical latent
      gap in `LlmClient`'s own fallback-provider check), with 6 new tests
      in `test_turnstile.py` — confirmed to actually fail without the fix,
      not just pass with it. Also fixed `.env.example`'s own template bug
      that helped cause this: `KEY=   # trailing comment` lines are read
      literally by the `.env` parser when the value is otherwise blank
      (`APP_ENV`/`BASE_URL` inherited the comment text as their value on
      this same setup) — comments now sit on their own line above the key,
      and every optional non-string field (`LLM_FALLBACK_URL`,
      `LANGFUSE_HOST`, `MAX_ACTIVE_SUBSCRIBERS`,
      `FAILURE_NOTICE_AUTO_LIMIT`) is commented out by default rather than
      left blank, since blank breaks those specifically while working fine
      for a plain optional string or secret.
      `orchestrator`'s model-config entry is unused dead weight now (it has
      never made an LLM call since the agent-table fix) but could not be
      removed outright: `ModelsConfig`'s own validator requires every
      `AgentKey` to have one. Noted in `config/models.yaml` rather than
      silently left inconsistent; removing "orchestrator" from `AgentKey`
      itself is a separate, larger cleanup, not folded into this one.
- [x] Most external accounts provisioned; the real Neon database now has a
      schema and reference data — `f0cdd02`. Owner populated a real `.env`
      (Neon, Gmail app password, OpenWeatherMap, a market API, a sports
      API, TMDB, Unsplash, Pexels, Langfuse, and Groq — see the
      llm-gateway-groq entry). `Settings()` loads clean against it.
      With the owner's explicit go-ahead (this is the first real write
      this project has ever made to a database that isn't a throwaway
      Docker container): ran `alembic upgrade head` against the real
      Neon database — all 6 migrations applied, 35 tables created,
      verified by querying `information_schema.tables` directly, not just
      trusting Alembic's own "success" output. Then `--dry-run` first,
      then for real, `python -m app.jobs.seed`: 87 cities and 27 sources
      loaded, verified by count. Every other table (`users`, `editions`,
      `stories`, `articles`, `deliveries`, ...) is empty, as expected —
      nothing has signed up, built, or sent anything yet.
      **Still genuinely blocked:** no GCP project (nothing is deployed
      anywhere — Terraform has never been applied) and no Cloudflare
      Turnstile account (`TURNSTILE_SITE_KEY`/`TURNSTILE_SECRET_KEY` still
      blank, so the signup bot-check runs in its "skip outside prod" mode
      only). Every source in `sources` shipped `enabled = false` as of
      this entry — since resolved, see the source-terms-review Done entry.
- [x] Source terms review: 18 of 27 sources enabled, and two real defects
      the live run underneath it surfaced, both fixed — `b6d9821`.
      Technical review (robots.txt, feed reachability, valid dates, real
      extraction against a live article) was done for every remaining
      candidate first, cheaply and without any legal judgement, so legal
      review effort only went to ones that could actually work. Owner's
      call on every terms decision, not the model's:
      - **RBI** (tier 1): disclaimer page says nothing about redistribution,
        only linking/framing — treated as acceptable for press-release
        content on that basis.
      - **Indian Express**: explicit prohibition on redistribution found by
        reading the real terms text — left disabled.
      - **Al Jazeera**: same explicit-prohibition pattern as Indian
        Express, found the same way — left disabled for consistency,
        despite passing every technical check.
      - The remaining 17 (The Hindu, Hindustan Times, Times of India,
        Scroll.in, Mint, Economic Times, BBC News, The Verge, TechCrunch,
        Engadget, Polygon, Eurogamer, Variety, Hollywood Reporter,
        Pitchfork, Rolling Stone, Bollywood Hungama) carry only the
        standard "personal, non-commercial use" boilerplate every outlet
        checked this batch had — read narrowly it covers the reader's own
        access, not redistribution to subscribers, so this is a deliberate
        practical-risk acceptance for a small, non-commercial learning
        project, recorded as such in each source's own `notes`, not a
        confirmed-permissive reading of the terms.
      Re-seeded the real Neon database (`python -m app.jobs.seed`,
      dry-run first) after each config change; the real Collector then
      returned real articles across all 10 genres against the live sources.

      Two real defects only surfaced by actually running the pipeline
      against real data, not by the terms review itself:
      - **RBI's pubDate has no timezone offset** ("Thu, 17 Sep 2026
        19:00:00", no `+HHMM`), which `feedparser` cannot parse at all —
        every item was being silently dropped for no reliable
        `published_at`. Added `Source.fallback_timezone` (a real IANA
        zone, validated against `zoneinfo.available_timezones()`) and a
        narrow fallback in `app/sources/feeds.py`: only used when
        feedparser's own parse fails and a source has explicitly declared
        its own known timezone — never a guess about content, and never
        applied to a source that hasn't opted in. 6 new tests in the new
        `test_feeds.py` (this module had zero tests before), 3 more in
        `test_config.py` for the new field's validation.
      - **An unbounded cluster size**: a real 9-article "business" cluster
        (multiple outlets covering the same Tata Sons story) sent ~45,000
        characters to the Writer in one call and exceeded every pinned
        model's per-request token budget outright — not a rate limit, a
        single request rejected on its own. `app/agents/ranker.py` now
        caps `PooledStory.articles` at 4, tier-1 sources and freshest
        first (`MAX_ARTICLES_PER_STORY`), applied *after*
        `corroboration_for`/`score_cluster` see every real member — a
        capped story's recorded corroboration still reflects how many
        independent sources actually covered it, not the smaller list the
        Writer reads and cites. 2 new tests.

      Also swapped `config/models.yaml`'s Writer/Ranker model
      (`openai/gpt-oss-120b` → `qwen/qwen3.8-27b`) after live calls to the
      first showed a hard 8000-tokens-per-minute account limit that
      couldn't sustain even one genre's worth of calls, and separately cut
      `max_output_tokens` from 4096 to 900 after discovering qwen3.8-27b's
      own real cap on this account is exactly 1000 output tokens/minute —
      a single request asking for more was rejected outright, every time,
      regardless of retries. Both were found by reading the real error
      body in `llm_calls`, not guessed at. A live end-to-end
      `write_and_verify` call (real Writer + real Fact-checker, both
      `ok` in `llm_calls`) has now succeeded against the real pipeline;
      getting a full section's `min_stories` met reliably is still
      contended by this account's tight real per-minute budgets under
      repeated manual testing — expected to be materially less of a
      constraint under the real scheduled job's own pacing (an hour-plus
      window, real network latency between calls) than under back-to-back
      manual test runs, but that is not yet itself proven.

- [x] Second LLM provider wired in for non-pinned agents, to survive Groq's
      real per-minute exhaustion — `aacd486`.
      - The user pasted a standalone `llm_router.py` at the repo root plus
        9 new provider keys (Cohere, Cloudflare, Mistral, Cerebras,
        SambaNova, NVIDIA, OpenRouter, Gemini, HuggingFace) and asked to
        "configure this... so we don't keep hitting the limit." That
        script was **not** wired in: it calls the `openai` SDK directly,
        which `app/llm/client.py`'s own docstring explains this project
        avoids specifically because the SDK's transport can't be
        intercepted by the test suite's respx mocking; it also has no
        audit trail, no personal-data guard, and a string-based API
        instead of this project's `Message`/`ModelSpec` types. Its own
        hardcoded model ids were live-tested and are already wrong for
        Groq, Gemini, and NVIDIA.
      - Tested all 9 new keys live (same method as the earlier Groq
        catalog check — the real endpoint, not docs). Only two work at
        all right now: Gemini (`gemini-3.6-flash`; the script's
        `gemini-2.5-flash` is retired) and Cloudflare Workers AI (tiny
        10k-neurons/day budget). Dead on this account: Cerebras and
        HuggingFace (402, no billing/credits), NVIDIA (410, model
        end-of-lifed), Mistral (429, already at 0 req/min), OpenRouter
        (free tier is 50 requests/**day**, account-wide, not per-model —
        too small to matter), SambaNova (429, transient overload).
      - Found a real design gap in the existing single-fallback-provider
        slot (`LLM_FALLBACK_URL`/`LLM_FALLBACK_API_KEY`): `routes_for()`
        reused the primary gateway's `model`/`fallbacks` list on the
        fallback gateway too, which only works if the fallback happens to
        share the primary's model names — false for Gemini. Added
        `ModelSpec.fallback_model` (a distinct model id for the fallback
        gateway only; rejected on a pinned agent, same as `fallbacks`) and
        changed `routes_for()` to route to the fallback gateway using
        that field instead of reusing `models`. Writer and Fact-checker
        stay pinned and untouched — no fallback route for either, by
        design. Wired Gemini in as `LLM_FALLBACK_URL`/`LLM_FALLBACK_API_KEY`
        in `.env`, and set `fallback_model: gemini-3.6-flash` on `ranker`
        and `image_finder` in `config/models.yaml`, the two non-pinned
        agents with a real caller. Verified the resolved routes live
        (`routes_for("ranker")` → Groq primary ×2, then Gemini fallback
        with its own model id) and confirmed a live Gemini call succeeds.
        4 new/updated tests in `test_llm_client.py` and `test_config.py`.
      - `llm_router.py` itself: deleted at the user's request once the
        real fallback wiring above covered its purpose.

- [x] First real business-genre build attempt found and fixed two live
      infrastructure bugs, and moved Writer off Groq — `993f19b`.
      - **Idle-in-transaction crashes.** The first real end-to-end
        `python -m app.jobs.build --genre business` run (against real
        Neon, real RSS sources, real Groq/Gemini) died with
        `psycopg.errors.IdleInTransactionSessionTimeout` twice, in two
        different places: `app/jobs/locking.py`'s `job_lock()` opens an
        advisory lock and then holds its session for the whole job with
        no further statement; `app/jobs/build.py`'s `run_build()`
        fetches/creates the `PipelineRun` row and then does the same —
        both leave an open transaction sitting idle for the real minutes
        the collect/rank/write/verify phase takes, and Neon kills it
        before the write phase (persist/publish) ever runs. Fixed both by
        committing immediately after the one early statement, ending the
        transaction without releasing anything the lock actually needs.
      - Fixing `job_lock()` this way broke a different, subtler thing: an
        ORM `Session` returns its connection to the pool on `commit()`
        (proven with a `pg_backend_pid()` probe, not assumed), so a
        second `job_lock()` call could get the *same* physical connection
        back and trivially "acquire" a lock its own connection already
        held — caught by `test_a_second_holder_cannot_take_the_same_job_lock`
        actually failing once the commit was added. Fixed by switching
        `job_lock` to hold a raw `Connection` checked out directly from
        the engine (never returned to the pool until `.close()`), not an
        ORM `Session`, so the same physical backend is genuinely pinned
        for the lock's whole life.
      - **PgBouncer risk, found while investigating the above.** Neon's
        `DATABASE_URL` in `.env` is the pooled endpoint ("-pooler" in the
        hostname) — PgBouncer in transaction mode, which can hand the
        *next* transaction on the same client connection to a different
        physical backend, silently breaking a session-scoped advisory
        lock regardless of any SQLAlchemy-level connection pinning. Added
        `Settings.database_direct_url` (optional, falls back to
        `database_url`) and `app/db/engine.py`'s `get_direct_engine()` —
        Neon's direct endpoint (same string, "-pooler" removed), verified
        live via a `pg_backend_pid()` probe that stays stable across a
        commit, unlike the pooled one. `job_lock()` now uses this by
        default. Not yet covered by an automated test (would need two
        real Neon endpoints in CI); verified manually against the real
        account instead.
      - **Writer moved off Groq.** The same live build run showed
        `qwen/qwen3.8-27b`'s real per-minute budget (both ITPM and OTPM)
        rejecting almost every Writer call outright — only 1 of ~10
        attempted stories made it through in one run. Added a per-agent
        `gateway: primary | fallback` field to `ModelSpec` (which
        credential set — `LLM_GATEWAY_*` or `LLM_FALLBACK_*` — an agent's
        own `model`/`fallbacks` route through) so one pinned agent can sit
        on a different provider than another without a global gateway
        swap; `LlmClient.routes_for()` updated to match. Writer is now
        pinned to `gemini-flash-lite-latest` via `gateway: fallback`;
        Fact-checker stays pinned to Groq's `gpt-oss-20b` — deliberately
        not the same model, preserving the existing vendor-diversity
        reasoning. Tried `gemini-3.6-flash` first and reverted the same
        day: its real free-tier cap is 5 requests/minute/project/model,
        found by `/evals/run.py`'s full suite genuinely exhausting it, not
        a guess. `gemini-flash-lite-latest` took a 15-call rapid burst
        (json_object mode, realistic payload) with zero errors.
        `/evals/run.py`'s `groundedness` and `tag_accuracy` pass against
        it in isolation; both intermittently fail when run back-to-back
        with the other evals, because that exhausts Fact-checker's own
        Groq TPM budget — a real, separate, still-open bottleneck (see
        below), not a Gemini content-quality regression.
      - Re-ran the real build after both fixes: the Neon crash is gone,
        and Writer succeeded on **30/30** real calls (zero errors). The
        business genre still published nothing (`quiet_day`, 0 stories):
        Fact-checker (pinned to Groq's `gpt-oss-20b`, no fallback by
        design) now hit its own real TPM limit — 63 errors vs 5
        successes in that run. Moving Fact-checker off Groq the same way
        is the next step, in progress.
      - 2 test call sites updated (`test_build_job.py`'s
        `session_factory=` → `connect=`), no test coverage lost.

- [x] Fact-checker moved off Groq too, two real deterministic-checker bugs
      fixed, and the business genre published its first real revision —
      `63b9f4d`.
      - **Fact-checker's Groq bottleneck.** Live testing found
        `gpt-oss-20b`, `gpt-oss-120b`, and `gpt-oss-safeguard-20b` all
        share the *same* 8000-tokens-per-minute cap on this account (a
        family limit, not per-model-id — confirmed by identical "Limit
        8000" text in real `llm_calls.error` rows for two different
        model ids), so no swap within that family could help; a real
        build's Fact-checker phase had logged 63 errors against 5
        successes. `qwen/qwen3.8-27b` (now idle since Writer moved off
        it) did worse under the same fact-check-shaped burst test (4/15
        OK — its 1000 OTPM cap binds harder in practice than gpt-oss's
        8000 TPM).
      - Added a **third named gateway**: `ModelSpec.gateway` extended
        from `primary | fallback` to `primary | fallback | secondary`,
        with new `Settings.llm_secondary_url`/`llm_secondary_api_key`
        (`LlmClient._gateway_creds` generalised to match). Fact-checker
        is now pinned to Cloudflare Workers AI's
        `@cf/meta/llama-3.3-70b-instruct-fp8-fast` via `gateway:
        secondary` — a third, genuinely different vendor from both Groq
        (Ranker) and Gemini (Writer's fallback gateway), preserving the
        vendor-diversity reasoning the config already documented for
        Fact-checker vs. Writer. Verified live: 20/20 calls under
        realistic fact-check-shaped burst load, zero errors. Free tier
        is ~10,000 neurons/day account-wide (~500 calls/day at this
        payload size) — ample for one real build, tight under repeated
        manual testing across many genres in one day.
      - Also fixed `ranker`/`image_finder`'s `fallback_model`, still
        pointing at the reverted `gemini-3.6-flash` from the previous
        entry — now `gemini-flash-lite-latest` like Writer.
      - **Two real deterministic Fact-checker bugs**, found only once
        Writer/Fact-checker were both actually succeeding often enough
        to expose them (previously masked by rate-limit noise):
        1. `names_in()`'s connector-joining regex treats a Title-Case
           headline (every word capitalised, by newspaper convention) as
           one giant "name" once the leading word is dropped — first
           patched with a 5-word length cap (fixed the original
           7-word case), but two more real headlines still false-
           flagged at 4-5 words each, proving a length cap alone cannot
           tell a genuine multi-word name from a headline. The actual
           fix: `unsupported_facts()` gained `check_names: bool = True`,
           and `FactChecker._deterministic` passes `check_names=False`
           for the `headline` element specifically — every real failure
           of this shape was in the headline; summary/why_this_matters
           are normal-case prose and keep the check. The model check on
           the same element remains the catch for a genuinely invented
           headline name (already 1.00 on `fact_checker_catch_rate` for
           exactly that planted-error category).
        2. A hyphenated headline join ("Mumbai-Ahmedabad corridor") for
           a source written as prose ("...between Mumbai and
           Ahmedabad...") failed the exact-substring name check even
           though both halves are individually grounded. Fixed:
           `unsupported_facts` now also accepts a hyphenated name when
           every hyphen-separated half appears in the passages.
        6 new/updated tests in `test_fact_checker.py` and
        `test_llm_client.py`.
      - **groundedness went from FAILing (0.80, then blocked entirely by
        `LlmUnavailableError`s from the old Groq contention) to PASSing
        (0.90) after both fixes** — all 8 evals pass. One real, separate
        finding along the way: Cloudflare's fact-checking judgment is
        noticeably stricter about exact paraphrase wording than Groq's
        was (flagged "construction" as unsupported when the passage said
        "the project", in one eval run) — a content-calibration
        difference between providers, not a bug; the real
        `write_and_verify` retry loop (not exercised by this single-pass
        eval script) would likely resolve most instances of this by
        asking Writer to hew closer to the passage's own words.
      - **First real end-to-end business-genre build succeeded**: real
        RSS sources → real Ranker (Groq) → real Writer (Gemini) → real
        Fact-checker (Cloudflare) → 2 verified, real stories (Tata Sons
        board reappointment; a US tariff bill) → published revision 1.
        Every one of the 7 real LLM calls in that run succeeded (2
        ranker, 3 writer, 2 fact_checker, 0 errors) — the first time
        this pipeline has completed against live data without hitting a
        rate limit, a crash, or a false-positive rejection.

- [x] The 2-story revision above was too thin for a real newsletter — found
      and fixed the actual cause, a Collector source-starvation bug, not a
      quiet news day — `405cc89`.
      - The user's own reaction ("that's not what i expected... who would
        like to read two stories?") was the right call. Diagnosed rather
        than assumed: `Collector.collect()`'s `DEFAULT_MAX_ARTICLES = 40`
        cap is shared across every enabled source, applied in the literal
        order sources are listed in `config/sources.yaml` — `for item in
        items: if len(articles) >= cap: break`. The Hindu's dedicated
        business feed alone supplied 35 fresh, valid articles that day,
        Hindustan Times added 5 more (35+5=40=cap), and the loop broke
        before Livemint's or Economic Times' feeds — two of the five
        enabled business sources — were ever even fetched. Confirmed live
        with a source-by-source breakdown of one real `collect('business')`
        call (`the-hindu: 35, hindustan-times: 5`, nothing else), not
        guessed at.
      - Separately, Livemint's *only* feed tagged `genre: business` was
        `rss/news` — Mint's general news feed (verified live: its actual
        items were a truck-driver stabbing, a school shooting, a pit-bull
        attack — essentially no business content at all), not a business
        feed. Real business feeds exist and were verified live the same
        day: `rss/money`, `rss/companies`. Both now feed the business
        genre; `rss/news` is no longer used anywhere.
      - Fixed the starvation bug generally, not just for business: added
        `Collector._round_robin()`, interleaving gathered feed items by
        source before the cap is applied, so a low-volume source's first
        item is never more than one slot behind a high-volume source's,
        however many items either has. 5 new unit tests in
        `test_collector.py`.
      - Re-verified live end to end. Source spread for a fresh
        `collect('business')` call went from `the-hindu: 35,
        hindustan-times: 5` (livemint and economic-times: 0) to
        `the-hindu: 11, livemint: 10, economic-times: 10, hindustan-times:
        9` — all four enabled sources represented. The ranker's candidate
        pool went from 2 stories to 9; a real end-to-end build for
        edition_date 2026-10-02 published **6 verified stories** (Apple's
        India launches, a pay-commission dispute, Apple Pay/Axis Bank,
        Buffett's Berkshire succession, a markets close, a Supreme Court
        inheritance case) — squarely inside CLAUDE.md's target of 4-6 per
        genre, not just above the 2-story "quiet day" floor.

- [x] Checked every genre for the same starvation pattern; found and fixed
      a real single-source gap in sports and bollywood — `78ac9f2`.
      - Ran a live `collect()` for all 10 genres. The round-robin fix
        above holds everywhere: no genre shows a source stuck at zero
        articles because of cap ordering. `business`'s `rbi: 0` is the
        already-documented, unrelated table-HTML extraction limitation,
        not this bug.
      - Found a different, real gap while checking: `politics`
        (scroll-in only), `sports` (the-hindu only), and `bollywood`
        (bollywood-hungama only) each had exactly one enabled source —
        round-robin cannot help when there is nothing to interleave
        against, and CLAUDE.md's corroboration rule needs "≥2 independent
        sources, or one primary official source" for the same reasons
        this file already gives the-hindu's own `terms_url` a stale-404
        caveat: a single source is a ceiling on how many stories can ever
        clear that bar.
      - Cheapest fix first: checked whether already-enabled, already
        terms-confirmed outlets had dedicated feeds for these genres
        sitting unused (the same shape of gap Livemint's business feed
        had). Found two, both verified live (fresh items, robots.txt
        allows): Hindustan Times' `feeds/rss/sports/rssfeed.xml` (general
        sports, broader than the-hindu's cricket-only one) and
        `feeds/rss/entertainment/bollywood/rssfeed.xml`. Added both to the
        existing hindustan-times entry — no new terms review needed, since
        that source is already reviewed. `sports` and `bollywood` each now
        have 2 independent sources; verified live
        (`sports: {the-hindu: 20, hindustan-times: 20}`, `bollywood:
        {hindustan-times: 27, bollywood-hungama: 12}`).
      - `politics` is still one source. Checked Hindustan Times' and The
        Hindu's real feed directories for a dedicated politics feed: HT's
        `elections/rssfeed.xml` looked promising by name but is stale
        (channel title only, no items); no autodiscoverable RSS link was
        found on either outlet's politics section page. Left open rather
        than guessing further at URLs — needs either more feed-URL
        hunting on already-enabled outlets, or a genuinely new source
        through the same terms-review process, next.

- [x] `politics` given a real second source — `indian-express` enabled,
      also giving `india`/`technology`/`bollywood` its already-drafted
      feeds — `da2e20a`.
      - `indian-express` was already drafted in `config/sources.yaml`
        with four feeds (india, **political-pulse → politics**,
        technology, bollywood) but had never been reviewed —
        `terms_confirmed`/`robots_checked`/`enabled` were all unset, no
        `notes`. Checked PIB (Government of India's own press releases)
        first as a primary-source alternative: technically unusable as
        configured — its feed has no `pubDate` at all (every item would
        be dropped for lacking a reliable timestamp, per the Collector's
        own "never guessed at" rule) and its content is Hindi, not
        English.
      - `political-pulse` verified live: fresh, real, balanced coverage
        across parties (BJP, Trinamool, Election Commission), robots.txt
        allows the article paths, and extraction gets ~8,400 clean
        characters from a real article. The other three already-drafted
        feeds checked too (fresh items, 200 OK) before enabling the
        source, since `enabled` is source-wide, not per-feed.
      - **Read the actual terms before enabling, not just assumed
        permissive like the earlier batch.** indianexpress.com's terms
        (dated 27 Dec 2021, explicitly covering RSS access) go well past
        the vague "personal, non-commercial use" language the rest of
        `config/sources.yaml` was read under — section 9.3 names AI use
        directly: prohibits creating "summaries, compilations, derivative
        works" from the content, and using it "for AI training,
        summarization" without "a binding licensing agreement, including
        fair monetary compensation." That is exactly what the Writer
        agent does to every article. Flagged this explicitly as a
        different category from the earlier practical-risk reading (the
        same bright-line treatment Al Jazeera's explicit prohibition got)
        and asked before enabling; the owner's call was to enable anyway,
        recorded verbatim in the source's own `notes` so this isn't
        mistaken for an oversight later.
      - Verified live: `collect('politics')` now returns
        `{'indian-express': 4, 'scroll-in': 24}` — a real second,
        independent source where there was one before.

- [x] Fact-checker got a narrow availability-only fallback, after
      Cloudflare's free tier turned out to be a DAILY cap, not per-minute
      — `7d41e9f`.
      - Testing a real multi-genre build (politics/sports/bollywood
        together) hit persistent 429s from Cloudflare that did not
        recover even after waiting. The real error body said why:
        "you have used up your daily free allocation of 10,000 neurons"
        — a whole-day cap, exhausted by this session's own testing
        volume (business runs, /evals/run.py runs, many diagnostics),
        not a per-minute throttle that backs off and recovers.
      - This blocks re-testing the same day it happens, with no
        workaround except waiting for the next UTC day. Asked before
        touching the pinning rule, since `ModelSpec` and its tests
        explicitly enforce "pinned = exactly one route, ever" for
        exactly the reason CLAUDE.md gives for Writer and Fact-checker
        together. Chose the narrower of two designs offered: an
        availability-only escape hatch, not unpinning Fact-checker
        outright.
      - Added `ModelSpec.availability_fallback_model` /
        `availability_fallback_gateway` — deliberately separate from
        the existing `fallback_model` (which is for non-pinned agents
        and tried unconditionally). `routes_for()` is unchanged and
        still returns exactly one route for a pinned agent — the
        contract a healthy primary always sees stays intact.
        `LlmClient.complete()` reaches for the escape hatch in a new
        `_try_routes()` helper only when every attempt on the primary
        route failed with a *retryable* error (429/5xx) — never for a
        fatal one like a malformed request, which the fallback provider
        would likely fail on too, and which isn't what "the primary is
        unavailable" means.
      - Fact-checker's escape hatch is Groq's `gpt-oss-20b` — its own
        original model, before the move to Cloudflare, and already-
        configured infrastructure (the existing `primary` gateway, no
        new secrets). 5 new tests (`test_llm_client.py`,
        `test_config.py`) cover: falls back after availability errors,
        does NOT fall back after a fatal one, and `routes_for()` staying
        at exactly one route regardless.
      - Verified live, for real, not just mocked: with Cloudflare's
        quota genuinely exhausted at the time, calling
        `LlmClient.complete("fact_checker", ...)` returned
        `provider='primary', model='openai/gpt-oss-20b'` — the escape
        hatch engaged on a real, live outage, not a simulated one.

- [x] Ran a real end-to-end build for every genre reachable today; 6 of 9
      published real, verified stories — `583ea3b`.
      - `business`: 6 stories (the first proven end-to-end run, recorded
        above). `india`: 2. `technology`: 3. `sports`: 3. `bollywood`: 3.
        All real content, real sources, real citations, published
        revisions — see each genre's `stories` table for
        edition_date 2026-10-01 through 2026-10-06.
      - `politics`: genuine `quiet_day`, not a bug. Pool size 0 —
        Indian Express (4 articles) and Scroll.in (28) simply did not
        cover the same underlying story on the day tested. The
        corroboration gate did exactly its job.
      - `ai`: looked like `quiet_day` but is not one. `llm_calls` for that
        run: `writer` 30/30 ok (Gemini, completely healthy) but
        `fact_checker` only 2/158 ok across BOTH its routes — Cloudflare
        still daily-exhausted, and Groq (Fact-checker's own availability
        fallback, same shared `gpt-oss` family Ranker's own fallback also
        uses) now also saturated from this session's cumulative testing
        volume across business/india/technology/sports/bollywood, all in
        one sitting. The architecture behaved correctly throughout —
        Writer stayed isolated on its own gateway, Fact-checker tried
        both its routes before giving up, the build correctly refused to
        publish rather than send anything unverified — this is a real
        capacity ceiling from today's test volume, not a defect.
      - `gaming`, `hollywood`, `music`: not tried, expected to hit the
        same exhaustion. Retest once Groq's and Cloudflare's quotas
        reset (Cloudflare: next UTC day; Groq: per-minute, recovers on
        its own once testing stops for a while).

- [x] **`EDITION_LAUNCH_DATE_OVERRIDE`: local testing no longer has to touch
      the real, still-provisional `launch_date`.** Owner's direction: the
      project stays untested-locally-then-decide-a-real-date until it runs
      "exactly how I want," not the other way round — `launch_date` and
      similar provisional values need to be freely changeable during
      testing, separate from the one real value that actually gates going
      live. `load_editions()` (`app/config/loader.py`) now reads this env
      var and, outside prod, overrides the loaded `launch_date` in place —
      `config/editions.yaml` itself is untouched, so the committed
      PROVISIONAL value is never edited back and forth just to test. Raises
      loudly if the var is left set with `APP_ENV=prod` (same posture as the
      Turnstile "skip outside prod, fail loudly in prod" check in
      `verify_turnstile`), rather than silently doing nothing — an override
      that quietly no-ops in prod is worse than one that doesn't exist,
      since it would look like it worked in every dev test. Documented in
      `.env.example`. 3 new tests in `test_config.py`: applies outside prod,
      refused in prod, and a no-op when unset (still resolves to the real
      shipped `2026-10-01`).

- [x] **Weather agent (7) built and wired end to end.** `app/services/weather.py`:
      no LLM, one HTTP call per city per `edition_date` (`weather_cache`
      already existed in the schema; nothing fed it until now), so N readers
      in the same city share one fetch and a later same-day delivery run
      reuses the morning's reading rather than calling again. Uses the
      existing `Fetcher` (retries/backoff/timeouts already built for the
      Collector) rather than a second HTTP client. Deliberate deviation
      recorded in the module's own docstring: CLAUDE.md calls this a
      "forecast," but OpenWeatherMap's actual daily-forecast product (One
      Call) needs a separate subscription tier beyond the plain free key
      CLAUDE.md provisions — this uses the always-free Current Weather
      endpoint instead (a real reading at build time, not a predicted
      high/low), rather than silently claiming more than it delivers or
      blocking on an account step nobody asked for.
      Wired into `app/jobs/delivery.py`: a new `weather_for()` resolves to
      `None` whenever weather can't or shouldn't be fetched (no city on the
      account, no `OPENWEATHERMAP_API_KEY` configured, or — since `main()`
      only opens a `Fetcher` at all when a key exists — no fetcher running
      for this job), so a missing reading is cosmetic, never a reason to
      skip or fail a reader's edition, the same posture as every other
      extra. `EmailRenderer`/the templates already accepted a `Weather`
      object and rendered the masthead box; only the feed was missing.
      7 new tests: `test_weather.py` (fresh fetch caches, a second call for
      the same city/date doesn't refetch, a failed fetch and a malformed
      response both return `None` instead of raising) plus two in
      `test_delivery_job.py` (the box appears with real content when a key
      and fetcher are configured, and is simply absent without one) — all
      against a real Postgres, all existing delivery tests (32) still pass
      unmodified. Verified live, for real: called the real OpenWeatherMap
      API with the project's own key for Mumbai's coordinates and got back
      genuine current conditions (32°C, scattered clouds), not a mocked
      response.

- [x] **Quote of the day and "On this day" built and wired end to end** —
      the first real use of the `extras` table, which existed in the schema
      since the initial migration but had nothing writing to it (the AI
      tool of the day extra deliberately bypassed it — see that Done entry
      — since it belongs to a single genre's section; these two are
      edition-wide, so `extras` fits as originally designed). No LLM,
      no API key needed — both come from Wikipedia's and Wikiquote's own
      free public feeds — CC BY-SA, attributed in the rendered email with a
      link back to the source page, per CLAUDE.md's Data sources section.
      `app/services/quotes.py`:
      - `fetch_on_this_day` calls Wikipedia's own public REST feed
        (`/api/rest_v1/feed/onthisday/selected/{mm}/{dd}`, no key), and
        takes the first (most significant, by Wikipedia's own curation)
        entry.
      - `fetch_quote_of_the_day` computes the day's Wikiquote page title
        (`Wikiquote:Quote of the day/{Month} {day}, {year}`, matching the
        `{{CURRENTMONTHNAME}} {{CURRENTDAY}}, {{CURRENTYEAR}}` transclusion
        the Main Page itself uses — confirmed by reading that transclusion
        live rather than guessing the page-naming scheme), fetches its raw
        wikitext via the MediaWiki action API, and parses the `quote`/
        `author` template parameters, stripping wikilinks (`[[a|b]]` ->
        `b`), `<br />`, HTML comments, and bold/italic markup — a value
        that doesn't parse (missing field, unexpected shape) is treated as
        "no reliable source today," never guessed at.
      - `persist_daily_extras(session, edition_date, fetcher)`: fetches
        and stores each kind at most once per `edition_date` — a rerun
        leaves an already-persisted kind alone rather than re-fetching
        (the content doesn't change intraday, and a rerun should never
        risk trading a morning's good reading for an afternoon's transient
        failure), and a kind whose fetch fails is simply omitted, same
        posture as every other extra ("a missing item is acceptable; a
        wrong one is not").
      Wired into `app/jobs/build.py` (`run_build` gained `extras_fetcher`,
      reusing the same `Fetcher` instance the Collector already uses —
      Wikipedia/Wikiquote aren't in `sources.yaml`'s whitelist since they
      aren't news sources, and `Fetcher` itself has no such restriction,
      only `Collector` does) and `app/jobs/delivery.py` (loads the two
      persisted rows once per run, not per reader, and passes them straight
      through — same shape as `weekend_content`). `EmailRenderer` and both
      templates gained `quote`/`on_this_day` blocks next to the weather box.
      11 new tests: `test_quotes.py` (both extras persist on a fresh
      build, a rerun doesn't refetch either, a failed quote fetch doesn't
      block "on this day" from persisting, a malformed response from
      either is omitted rather than raised) plus two each in
      `test_build_job.py` and `test_delivery_job.py` — all against a real
      Postgres; the full suite (659 tests) and `mypy`/`ruff` stay clean.
      Verified live, for real: fetched today's actual Wikiquote quote
      (Francis Turner Palgrave, correctly preserving its real em dash —
      the `�` seen in one terminal printout was that console's own
      encoding, not a bug, confirmed by writing the string to a UTF-8 file
      and checking its actual code points) and Wikipedia's real "on this
      day" entry for today (the Sycamore Gap tree felling, 2023).

- [x] **All 10 genres now proven end to end for real, for the first time.**
      The previous real-build session got 6 of 9 (`gaming`/`hollywood`/
      `music` untried, `ai` blocked) because that day's Cloudflare/Groq
      quota was exhausted by the session's own testing volume. Retried
      today (a fresh UTC day resets Cloudflare's cap): `ai` (7 stories,
      `2026-10-07`), `gaming` (5, `2026-10-08`), `hollywood` (5,
      `2026-10-09`), `music` (4, `2026-10-12`) — all published cleanly, no
      quota errors. Every genre CLAUDE.md lists has now published real,
      verified, cited stories at least once.
      - One real infrastructure lesson from this batch, not a code bug:
        the `gaming` build's first attempt was killed by an over-eager
        280-second shell-level `timeout` wrapper around the command before
        the Fact-checker's retry loop (real API calls, real backoff) could
        finish — the job itself was still healthy, just cut off mid-run,
        leaving an orphaned `RUNNING` `pipeline_runs` row (harmless; a
        fresh retry gets its own `run_id`). Genre builds with heavier
        Fact-checker retry traffic can genuinely run past 5 minutes end to
        end; don't wrap them in a tight external timeout.
      - Also rendered one full real email end to end (a throwaway local
        subscriber, deleted immediately after, via a recording `Sender`
        subclass so nothing was actually emailed) for the `ai` edition:
        masthead, live weather ("Mumbai: Light rain, 31–31°C" — the real
        Weather agent), the "On this day" box with its real Wikipedia
        content and source link, "Today in 60 seconds," the full section
        with all 6 verified AI stories and their real source links, the
        PDF link, and unsubscribe — the first time this project's actual
        email output has been read rather than only asserted on in tests.
      - **Found a real, previously-unknown limitation while doing this:**
        Wikiquote's "Quote of the day" only has pages authored up to
        roughly the present date — every one of these test dates (chosen
        to land after the six already-published test editions) is a few
        days to two weeks in the future relative to *this* session, so the
        day's QOTD subpage doesn't exist yet and `fetch_quote_of_the_day`
        correctly logged a warning and omitted the box each time, while
        "On this day" (which needs no page to exist in advance — Wikipedia
        answers any month/day) succeeded every time. Not a bug: this is
        exactly the designed "omit rather than guess" behaviour, now
        confirmed against real production dates rather than only against
        mocked responses. Real calendar dates (today onward, once the
        project actually launches) will have their QOTD page like any
        other day; only these synthetic future test dates don't.

- [x] **Market strip built — scoped down from CLAUDE.md's implied
      Nifty/Sensex to USD/INR only, after actually reading three providers'
      terms rather than assuming any of them permit newsletter use.**
      - The owner's already-provisioned `MARKET_API_KEY` was identified
        (by testing it against candidate endpoints, since nothing recorded
        which provider it belonged to) as a genuine Twelve Data key, on
        their free "Basic" plan. Confirmed live: `NSEI` (Nifty 50),
        `BSESN` (Sensex), and every NSE/BSE equity or ETF tried (including
        Nifty-tracking ETFs) return *"This symbol is available starting
        with the Grow or Venture plan"* — Indian market data specifically
        needs a paid tier. `MARKET_API_KEY_2` doesn't authenticate as a
        Twelve Data key at all and is unused by `Settings`; its purpose is
        unknown.
      - Before building anything against the free-tier data that *is*
        reachable (forex/commodities), actually read Twelve Data's Terms
        of Service, per CLAUDE.md's "confirm its terms allow display in an
        email newsletter" rule — and found the real blocker isn't
        data-tier coverage at all: their "Redistribution" is defined as
        *"any publication, distribution, or provision of Data to third
        parties,"* permitted only "as expressly permitted by your
        Subscription Tier, **Redistribution Rights Add-On**, or separate
        agreement" — a distinct, paid-separately right that gates putting
        *any* of their data (not just equities) into a newsletter. Checked
        the obvious alternative, Alpha Vantage, the same way: its free
        license is "personal, non-commercial use," and its own definition
        of "commercial use" explicitly includes "provid[ing] information
        accessed through the [Platform] as part of any type of commercial
        activity that allows individuals or entities other than User to
        access information" — a newsletter, again, squarely.
      - Asked the owner before building on a provider whose terms don't
        clearly allow it (twice — first when the Indian-data limitation
        surfaced, again when the redistribution-rights issue surfaced) and
        was asked to keep looking rather than build around it. Found one
        source with an actual, explicit, checkable permission: the
        **European Central Bank**'s own daily reference exchange rates,
        via **Frankfurter** (MIT-licensed, no API key). ECB's copyright
        notice: *"users of this website may make free use of the
        information obtained directly from it"*, conditioned only on
        accurate reproduction and citing the ECB as the source — read
        directly from `ecb.europa.eu`, the same diligence
        `source-terms-review` gave every news source in `sources.yaml`.
        This covers currency rates only, so the strip is **USD/INR alone**
        — no indices, no gold — until a provider with equivalent terms for
        those is found or a paid redistribution right is purchased.
      - `app/services/markets.py`: `fetch_market_strip` calls
        Frankfurter's `/v1/latest?base=USD&symbols=INR`; `persist_market_strip`
        stores it once per `edition_date` in `extras` (the same
        check-exists-skip idempotency as the quotes/on-this-day extras —
        a rerun never re-fetches an already-persisted day). ECB publishes
        once per business day and not on weekends/TARGET holidays;
        Frankfurter's own `/latest` already returns the last published
        day's rate with its own date on those days, so CLAUDE.md's "on
        market holidays and weekends it shows the last close with its
        date" needed no custom handling — same pattern as the weather and
        quotes extras before it.
      - Wired into `app/jobs/build.py` (reuses the same `extras_fetcher`
        as the other two daily extras) and `app/jobs/delivery.py` (loaded
        once per run, not per reader). `EmailRenderer` and both templates
        gained a `market` block next to weather/quote/on-this-day, showing
        the rate, its date, "ECB," and a "not investment advice" note —
        the exact three things CLAUDE.md's market-strip line requires.
      - 9 new tests: `test_markets.py` (fresh fetch caches, a rerun
        doesn't refetch, a failed fetch and a malformed response both
        omit rather than raise) plus one each in `test_build_job.py` and
        `test_delivery_job.py` (present when persisted, absent when not)
        — all against a real Postgres; full suite now 664 tests, all
        passing, `mypy`/`ruff` clean.
      - Verified live, for real: fetched the actual current USD/INR rate
        from Frankfurter (₹95.82, dated 2026-09-25 — a Friday, since ECB
        doesn't publish on the Saturday/Sunday this was run on, exactly
        the weekend-fallback behaviour CLAUDE.md describes, observed for
        real rather than simulated) and confirmed it renders correctly in
        a real assembled email alongside the weather and "On this day"
        boxes.

- [x] **Image finder (agent 6) built — the last of the 10 agents, and (with
      it) the last item in CLAUDE.md's Newsletter-extras/genre-extras lines
      that had no code at all.** Two scope questions were asked and
      answered before writing anything, the same way "AI tool of the day"
      was scoped: (1) one image per genre section, attached to that
      section's top-ranked story only — not one per verified story, which
      would have multiplied API and LLM-relevance calls by up to 6x per
      genre for a rarely-decorative payoff; (2) CLAUDE.md's "use the
      genre's default artwork" fallback is **not** built, since no such
      artwork — not even a config field naming one — exists yet; a missing
      image is simply omitted, same posture as every other extra, until
      real illustrations exist as a separate piece of work.
      - `app/agents/image_finder.py`: text-only LLM relevance check (the
        model never sees the image itself, only each candidate's own
        caption/description — matching the agent table's "Yes (text only)
        + code" exactly), over search results from Wikimedia Commons,
        Unsplash, and Pexels. Commons candidates are filtered against an
        explicit allowlist of clearly-reusable license short names (CC0,
        public domain, plain CC BY/CC BY-SA variants) — anything else,
        including unclear or non-commercial licenses that do turn up on
        Commons despite its free-license policy, is rejected rather than
        trusted. `app/llm/prompts/image_finder_v1.py` is the new prompt;
        its own instruction is explicit that a generic or merely-plausible
        photo is not a match — confirmed against the real model, not just
        asserted: given "India wins the cricket World Cup final" against 8
        real candidates including several generic India-cricket photos,
        it correctly returned no match rather than guessing, and given a
        more literal headline ("A cricket match takes place in India") it
        correctly picked and credited a genuinely matching Pexels photo.
      - `app/sources/fetch.py`'s `Fetcher.get()` gained an optional
        `headers` parameter (additive to, never replacing, the default
        User-Agent) — Unsplash and Pexels both require an `Authorization`
        header, which nothing before this needed. Caught and fixed a
        review's-worth of own damage along the way: an early edit to
        `test_fetch.py` left one line of an *existing* test dangling
        inside the *new* test that followed it (a stray
        `assert route.call_count == 1`, silently still passing because it
        happened to reference the new test's own same-named local
        variable) — fixed before it could ship, new coverage added for
        the header behaviour itself.
      - Every image is hotlinked from the provider's own URL, never
        rehosted, with a credit persisted via a new `persist_image()` in
        `app/db/persist.py` (the `images` table existed in the schema
        since the initial migration with exactly this shape — `story_id`,
        provider, license, credit — and had never been written to until
        now). Unsplash's API guidelines require pinging a download-
        tracking endpoint when a photo is actually used (not merely
        returned by search); `_track_unsplash_download` does that only
        for the candidate actually chosen, and its own failure is logged,
        never allowed to cost a reader their story's image.
      - **Ordering was the real design constraint, not the API calls
        themselves**: `app/jobs/build.py`'s own docstring already recorded
        "every LLM call happens before the database is touched... the
        write phase is short and can be one transaction" — a rule that
        exists because an idle-in-transaction session once got a real Neon
        connection killed (see the `llm_calls`-logging Done entry). The
        Image finder's relevance check is an LLM call, so it runs in the
        same pre-persist phase as Writer/Fact-checker (right after
        `orchestrator.build()` returns, before any `persist_*` call), not
        interleaved with the open write transaction the persist loop
        holds. `persist_genre` gained a sibling, `persist_genre_stories`,
        returning the stored `Story` rows (index 0 = top-ranked) instead
        of just a count — `persist_genre` itself, and every one of its
        many existing callers/tests, is completely unchanged.
      - `app/render/sections.py`'s `SectionRenderer.render()` gained an
        optional `image` parameter, rendered in `section.html.j2`/`.txt.j2`
        next to the existing AI-tool-of-the-day callout; `render_candidates`
        (the late-update re-render path) deliberately does not accept one
        — see the new "Not built yet" entry recording that as a scope
        limit, not an oversight.
      - 25 new tests (`test_fetch.py`: the new header parameter;
        `test_image_finder.py`: a relevant Wikimedia candidate is chosen
        and credited, an unlicensed one is rejected, Unsplash triggers its
        download ping only when chosen, Pexels is chosen and credited, no
        candidates from any provider skips the LLM call entirely, the
        model saying no match returns `None`, one failed provider doesn't
        block the others, entity tags are preferred over the headline for
        the search query and a story with none falls back to it, no API
        keys still tries Wikimedia alone; `test_sections.py`: the image
        and its credit render in both formats, no block when none was
        found, `render_candidates` never carries one; `test_build_job.py`:
        a full build attaches the image to the section's actual top story
        row and its HTML, and a build with no `image_finder_llm` attaches
        none) — all against a real Postgres where relevant; full suite now
        **680 tests**, all passing, `mypy` (142 files) and `ruff` clean.
        One real, previously-latent bug surfaced and fixed while writing
        these: three tests reused a `mock_empty_providers()` helper that,
        called *after* a test had already registered a more specific mock
        for the same URL pattern, silently overwrote it (respx treats
        identical route patterns as the same underlying object) — caught
        because the first such test's assertion genuinely failed, not
        because anything alerted on it; the other two were passing for
        the wrong reason (asserting `None` either way) until traced back
        and fixed the same way.

- [x] **Movie releases built for bollywood and hollywood — TMDB, exactly
      the provider CLAUDE.md already names, so no provider-choice research
      was needed this time. Terms still read before building, the same way
      as the market strip.** TMDB's free key is for non-commercial use;
      read their actual API Terms of Use rather than assuming, and their
      definition of "commercial" (charging users, running ads, or
      recommendation-driven revenue) does not describe this free,
      unmonetised newsletter, so the free key is the right fit — a real,
      substantive difference from Twelve Data/Alpha Vantage, not a
      coincidence of wording.
      - `app/services/releases.py`: one call to TMDB's `/movie/upcoming`
        per genre per `edition_date`, region-mapped (`bollywood` -> `IN`,
        matching its blurb's "Indian cinema" scope rather than Hindi-only;
        `hollywood` -> `US`), persisted in `extras` — the first extra
        scoped to a single genre rather than the whole edition (`Extra.genre`
        existed in the schema for exactly this, unused until now). Sorted
        by release date and capped at 3; entries missing a title or date
        are dropped rather than guessed at.
      - **Attribution is incomplete, on purpose, not by oversight.** TMDB's
        terms require both a specific text notice (included verbatim,
        confirmed against a real assembled section) *and* their logo,
        sized per their own prominence rules. Asked the owner rather than
        guess or skip silently: no reliable official logo asset URL was
        sourced, so only the text notice is shown for now — the logo
        requirement is an open compliance item, not a resolved one.
      - Wired into `app/jobs/build.py`'s per-genre persist loop (a plain
        HTTP call, not an LLM one, so unlike the Image finder it does not
        need the pre-persist-phase discipline) and `app/render/sections.py`
        (`SectionRenderer.render()` gained a `movie_releases` parameter,
        rendered in both formats next to the AI-tool-of-the-day callout).
      - 13 new tests: `test_releases.py` (a fresh fetch is sorted/capped/
        persisted, a rerun doesn't refetch, bollywood and hollywood persist
        independently, a non-movie genre and a missing API key are both
        skipped without a network call, a failed fetch and a malformed
        response and an empty result are all omitted rather than raised)
        plus two in `test_sections.py` and two in `test_build_job.py`
        (a real build attaches releases to a bollywood section's actual
        HTML with the attribution notice present, and a build with no TMDB
        key attaches none) — all against a real Postgres where relevant.
      - Verified live, for real, against the actual TMDB API: fetched
        genuinely upcoming India-region releases (a real mix of Hindi,
        Tamil, Telugu, Malayalam, Kannada, and Bengali titles — confirming
        the "Indian cinema," not "Hindi-only," region choice was the right
        read of the genre's own blurb) and US-region releases.

- [x] **Music releases built for the music genre — no new provider needed
      at all.** CLAUDE.md's own wording ("official label/platform
      announcements covered by whitelisted sources") already says this
      isn't a separate API the way movie releases are — it comes from the
      day's own verified music stories, the same mechanism as "AI tool of
      the day": `config/genres.yaml`'s music genre already has
      `album-releases`/`single-releases` in its closed topic-tag taxonomy,
      so `SectionRenderer` (`app/render/sections.py`) picks up to 3
      stories carrying either tag and renders them as a "New releases:"
      callout, in both the fresh-build path (`_music_releases_from_verified`)
      and the late-update/persisted-candidate path
      (`_music_releases_from_candidates`) — unlike movie releases and the
      Image finder, this costs nothing extra to support on both paths,
      since it needs no network call and no LLM call of its own, only the
      tags the Writer and Fact-checker already produced and verified.
      9 new tests in `test_sections.py`: a tagged story becomes a release,
      an untagged one doesn't, no callout for a non-music genre, a cap at
      3 with a 4th tagged story excluded, and the late-update path surfaces
      a tagged candidate too.
      Verified live, for real, against a genuine build (`2026-10-13`,
      `music`, 4 real verified stories): a real story — "U2 Announces 50th
      Anniversary Album Carnaval De Luz," sourced from Rolling Stone — was
      independently tagged `album-releases` by the real Writer/Fact-checker
      pipeline (no test fixture, no mock) and correctly surfaced in the
      persisted section's actual "New releases:" callout.

- [x] **Sports scores and fixtures built for the sports genre — three
      provider dead ends hit first, each a real finding, none guessed
      around.** CLAUDE.md asks for "a sports data API with cricket
      coverage" without naming one, unlike movie releases (TMDB); finding
      one took real back-and-forth with the owner rather than picking the
      first thing that returned data:
      1. The already-provisioned `SPORTS_API_KEY` turned out to be a
         CricAPI (cricapi.com) key (identified by its UUID-shaped format,
         which their own API echoed back) — every endpoint returned
         `"Subscription invalid"`. Resetting the key on their dashboard
         didn't change the `.env` value, and re-testing after didn't help.
      2. The owner then tried api-sports.io directly. Checked before
         building anything: **api-sports.io does not offer a cricket
         product at all** — `v1.cricket.api-sports.io` doesn't resolve,
         confirmed by checking real sport subdomains side by side
         (football/basketball/rugby/hockey all resolve; cricket doesn't).
         A separate, unrelated site at api-cricket.com does exist but uses
         its own distinct account system (`APIkey` query param, not
         api-sports.io's key) — the provisioned key didn't match it either.
      3. Recommended RapidAPI instead, specifically for a reason: its own
         platform terms centralise a single subscribe action and a single
         auth pattern (`x-rapidapi-key`), rather than each vendor's own
         separate "register, then separately subscribe to this specific
         product" dashboard flow that had just failed twice. The owner
         subscribed to Cricbuzz Cricket API there; the new key worked
         immediately, live, against both `/matches/v1/recent` (scores) and
         `/matches/v1/upcoming` (fixtures).
      - **Terms: checked, and the answer is genuinely unresolved — recorded
        as such, not assumed either way.** RapidAPI's own platform terms
        explicitly defer all data-usage rights to each API's own provider
        ("API Provider, not Rapid, is responsible for... the API
        Content/Terms applicable to each API"). Cricbuzz's own site is a
        JS-rendered SPA that did not yield explicit, checkable terms the
        way ECB's or Wikipedia's plain-HTML pages did. Presented this
        honestly to the owner — not "probably fine," not silently
        skipped — and built it on their explicit instruction, with the gap
        itself recorded here rather than closed by assumption. Revisit if
        Cricbuzz's actual provider-specific terms surface (e.g. the
        RapidAPI dashboard shows a terms tab only when logged into the
        subscribing account, which an anonymous fetch can't see).
      - **A real, narrow interoperability bug, found and fixed, not
        theorised:** this host's WAF (Akamai, fronting Cricbuzz's real
        backend) returns 403 for the project's standard `Fetcher` User-
        Agent — specifically its `"(+https://...)"` contact-URL
        parenthetical — confirmed by testing the exact same request with
        and without it. Fixed with a per-call header override (`Fetcher.get`
        already supported this, added for the Image finder's Unsplash/
        Pexels calls) rather than changing the shared default: this is a
        narrow bot-detection quirk on one authenticated, keyed API call,
        not the "a source that blocks an honest crawler is telling us not
        to fetch it" case the shared User-Agent exists to honour.
      - `app/services/sports.py`: one call each to Cricbuzz's `recent`
        (completed matches) and `upcoming` (fixtures) endpoints per
        edition_date, persisted as two separate `extras` rows
        (`ExtraKind.SCORE` / `ExtraKind.FIXTURE`, both `genre="sports"` —
        the schema already had two separate kinds for exactly this).
        Cricbuzz's own `status` field (e.g. "India won by 4 wickets") is
        used verbatim for scores rather than reconstructing a result
        sentence from raw runs/wickets — their pre-written text, not
        generated here. Sorted by recency (scores) or soonest-first
        (fixtures) and capped at 3 each.
      - Wired into `app/jobs/build.py`'s per-genre persist loop (sports-
        genre-only, a plain HTTP pair, not an LLM call) and
        `app/render/sections.py` (`SectionRenderer.render()` gained
        `scores`/`fixtures` parameters, rendered in both formats).
      - 15 new tests: `test_sports.py` (completed/upcoming matches
        extracted, sorted, and persisted correctly; a rerun doesn't
        refetch; no key and a failed or malformed fetch are all handled
        without raising) plus two in `test_sections.py` and two in
        `test_build_job.py` (a real build attaches both to a sports
        section's actual HTML; no key attaches neither) — all against a
        real Postgres where relevant; full suite now **707 tests**, `mypy`
        (146 files) and `ruff` clean.
      - Verified live, for real, twice: once as a direct fetch (India v
        Afghanistan, Bermuda won by 42 runs, real upcoming fixtures) and
        once through an actual build run (`2026-10-14`, `sports`) — the
        genre itself was a genuine quiet news day for verified stories
        that run (0 stories, a real corroboration-gate outcome unrelated to
        this work), but the score/fixture `extras` rows persisted
        correctly regardless, exactly as designed: extras don't depend on
        that day's story count.

- [x] **Game deals built for the gaming genre — the cleanest of the extras
      built this session, and the last genre extra CLAUDE.md names. Every
      genre extra now has code behind it.** CLAUDE.md names CheapShark
      directly as the example provider, so — like movie releases (TMDB) and
      unlike market data and sports — no provider search was needed.
      - CheapShark is free, public, and keyless — the only requirement is a
        descriptive User-Agent; a generic one is explicitly rejected by
        their API with a clear error, confirmed live. Their own business
        model is driving affiliate traffic through exactly this kind of
        third-party display, and their terms page carries none of the
        redistribution restrictions Twelve Data's, Alpha Vantage's, or
        TMDB's do — the cleanest data-rights picture of any extra built
        this session, checked the same way as the others, not assumed.
      - `app/services/deals.py`: one call to CheapShark's `/deals` endpoint
        (sorted by their own "Deal Rating" composite score, not a ranking
        invented here) plus one to `/stores` for human-readable store
        names, per edition_date. Deduplicated by title — the same game
        discounted at several stores otherwise crowds out real variety in
        the 3-item cap — and persisted in `extras`
        (`ExtraKind.GAME_DEAL`, `genre="gaming"`).
      - **A real bug, caught by its own test rather than shipped:** a
        malformed (non-list) API response crashed with an unhandled
        `AttributeError` — the original `try/except` wrapped the two fetch
        calls but not the processing loop that assumed a list of dicts.
        `test_a_malformed_response_is_omitted_instead_of_raising` failed
        against the real code before the fix (an explicit `isinstance`
        check, raising the project's own `DealsFetchError` instead), not
        after — the same "caught it, didn't just assert it" standard as
        every other test this session.
      - Also fixed before it ever ran live: `dealID` values come back from
        CheapShark's API already URL-encoded (their JSON literally contains
        `%2B`, `%2F`, `%3D` as characters); re-encoding it into the
        redirect URL would have double-encoded and broken every deal link
        silently. Caught by comparing a live fetch's output URL against the
        raw API response before wiring it any further, not by a test.
      - Wired into `app/jobs/build.py`'s per-genre persist loop (gaming-
        genre-only, a plain HTTP pair, no API key, no LLM) and
        `app/render/sections.py` (`SectionRenderer.render()` gained a
        `game_deals` parameter, rendered in both formats).
      - 16 new tests: `test_deals.py` (dedup and cap, an unknown store id
        gets a generic label rather than failing, a deal missing a
        required field is skipped, a fresh fetch persists, a rerun doesn't
        refetch, a failed fetch and the malformed-response bug above are
        both handled without raising) plus two in `test_sections.py` and
        two in `test_build_job.py` (a real build attaches deals to a
        gaming section's actual HTML with correctly-encoded links; no
        fetcher attaches none) — all against a real Postgres where
        relevant; full suite now **718 tests**, `mypy` (148 files) and
        `ruff` clean.
      - Verified live, for real, twice: once as a direct fetch (real Steam/
        Humble Store deals, e.g. "ENDLESS Legend 2" at 50% off) and once
        through an actual build run (`2026-10-15`, `gaming`, 7 real
        verified stories) — the real published section's HTML carries the
        genuine deals with correctly single-encoded redirect links, exactly
        matching the direct-fetch output.
      - **With this, every genre extra CLAUDE.md's config already declared
        (`config/genres.yaml`'s per-genre `extras` list — AI tool of the
        day, scores/fixtures, game deals, movie releases ×2, music
        releases) now has real code behind it, built and verified live
        against real data, not just against mocks.**

- [x] **Critical: six "Done" genre extras — including "AI tool of the day"
      from a previous session — never actually reached a real subscriber's
      inbox.** Found while trying to show the owner an actual generated
      newsletter, the same way the six-jobs-never-ran bug was found by
      actually running each job as a subprocess rather than trusting that
      `main()` existed.
      - `SectionRenderer` (`app/render/sections.py`) computes image/ai_tool/
        movie_releases/music_releases/scores/fixtures/game_deals, but it
        only ever runs at **build time**, producing the once-per-revision
        `EditionSection` the public archive reads. The actual delivered
        email is assembled separately, by `EmailRenderer` from per-reader
        `Candidate` objects — and `Candidate` never carried any of this
        data, nor did `email.html.j2`'s per-section loop render it. Proved
        this live before touching any code: ran the real delivery job
        against the real gaming/2026-10-15 edition (a genuine persisted
        image and game-deal extra), and the resulting email had neither.
        `app/render/sections.py`'s own module docstring had already said
        "Per-user assembly (masthead, extras, ordering) happens later, at
        delivery" — true for weather/quote/on-this-day/market (which really
        are computed in `delivery.py` and passed into `EmailRenderer`
        directly), false for these six. A real bug, not a design choice,
        confirmed against the docstring's own stated intent.
      - Fixed by giving every reader who selects a genre the same
        non-personalised extras that genre's build-time render already
        computed, the same way weather/quote/market already work:
        - `ai_tool_from_candidates`/`music_releases_from_candidates`
          (pure functions of `(genre, candidates)`, no other dependency)
          moved out of `SectionRenderer` into `app/render/selection.py`,
          next to `Candidate` itself, so both the build-time path
          (`SectionRenderer`) and the per-reader path (`EmailRenderer`)
          call the exact same logic instead of two copies that could drift.
          `SectionRenderer` itself is otherwise unchanged.
        - New `SectionExtras` dataclass (`app/render/email.py`): image,
          movie_releases, scores, fixtures, game_deals — the pieces that
          genuinely come from outside the reader's own Candidates (a DB
          image lookup, persisted `extras` rows). `EmailRenderer.render()`
          gained a `section_extras` parameter.
        - New `load_section_extras()` in `app/jobs/delivery.py`: looks up
          a genre's top story's `Image` row and its persisted movie-release/
          score/fixture/game-deal `extras`, for one genre at one
          edition_date. Computed **once per genre per delivery run**, not
          once per reader — cached in a plain dict across the reader loop,
          since none of this is personalised, only the story selection is.
        - The five HTML/text blocks (image, AI tool, movie releases, music
          releases, scores, fixtures, game deals) were duplicated between
          `section.html.j2`/`.txt.j2` and would have needed a second copy
          in `email.html.j2`/`.txt.j2`. Extracted into shared
          `_section_extras.html.j2`/`.txt.j2` partials instead, included by
          both — confirmed behaviour-preserving first (all existing
          `SectionRenderer` tests passed unchanged before any new feature
          code was added), so the one duplication this bug grew out of
          cannot recur the same way.
      - 6 new tests in `test_email_render.py` (AI tool of the day and music
        releases now derive correctly from a reader's own Candidates; a
        full `SectionExtras` renders image/movie-releases/scores/fixtures/
        deals in both formats; none of it appears when absent) plus 1 in
        `test_delivery_job.py` exercising the real delivery job end to end
        with a persisted image and game-deal extra reaching the actual
        assembled email; full suite now **724 tests**, `mypy` (148 files)
        and `ruff` clean.
      - Verified live, for real, both before and after: re-ran the exact
        same real delivery (gaming, `2026-10-15`) that first exposed the
        bug — the image and "Deals:" block were both absent before the fix
        and both present, with the correct photo credit and correctly-
        encoded CheapShark links, after it.
- [x] **Langfuse tracing is wired in.** New `app/llm/langfuse_recorder.py`:
      `LangfuseCallRecorder` (implements the same `CallRecorder` protocol as
      `DatabaseCallRecorder`, one Langfuse `generation` observation per LLM
      call attempt — metadata only: agent, model, provider, token counts,
      latency, status; never message content, since Writer/Fact-checker
      input is unpublished source text and CLAUDE.md never says that's safe
      to hand a third party), `BroadcastCallRecorder` (fans one `record()`
      call out to several recorders, so the database and Langfuse both see
      every attempt without either knowing about the other), and
      `build_call_recorder()` — the single factory both the build and
      late-update jobs now call instead of constructing
      `DatabaseCallRecorder` directly: always the database, Langfuse joining
      only when `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST`
      are actually configured, so nothing changes for a dev environment
      without them. Returns a small `RecorderBundle(recorder, flush)`; the
      `flush` is a real call to the Langfuse client's own `flush()` when
      Langfuse is wired (these are short-lived Cloud Run jobs, so nothing
      else would force its buffered spans out before the process exits) and
      a no-op otherwise, so both jobs can call it unconditionally in a
      `finally` block. A Langfuse-side failure is caught and logged, never
      raised — tracing must not break a build over an outage in the service
      that only exists to observe it.
      Verified against the real, already-provisioned account, not just
      mocked: built a real client from the actual `.env` keys, sent one real
      `record()` call, called `flush()`, then confirmed over Langfuse's own
      API (`auth_check()` true, `api.observations.get_many(name="writer")`
      returned the just-sent observation) that it actually landed on
      `cloud.langfuse.com` — not only that the SDK call didn't raise. 11 new
      tests in `test_langfuse_recorder.py`, all against fakes (a
      `FakeLangfuseClient`/`FakeObservation` standing in for the real SDK
      objects, and `DatabaseCallRecorder` itself monkeypatched out in the
      one test that exercises `build_call_recorder`'s wiring) so the unit
      suite stays free of any real network or database call; full suite
      (`TEST_DATABASE_URL` set, nothing skipped) now **764 tests passing**,
      `mypy --strict` and `ruff` clean.
- [x] **Neon-specific engine settings verified against the real Neon
      endpoint**, not reasoned about or run only against local Postgres.
      Two manual scripts (real `DATABASE_URL`/`DATABASE_DIRECT_URL` from
      `.env`, not committed — this needs the real, provisioned database, not
      something to run in CI):
      - `prepare_threshold=None`: reproduced the exact shape the code
        comment warns about — one long-lived client `Connection`, many
        separate transactions, well past psycopg's auto-prepare threshold
        (60 rounds) — with the override both on and off. **Zero errors
        either way.** Looked closer at why: Neon's PgBouncer is issuing its
        own `PGBOUNCER_N`-named prepared statements — PgBouncer's newer
        prepared-statement-passthrough feature (added ~1.21+), which
        transparently re-prepares across backend swaps in transaction-
        pooling mode. So the failure this setting guards against (a classic,
        older-PgBouncer limitation) no longer reproduces on Neon's current
        pooler — confirmed, not assumed. Separately killed a live pooled
        connection's backend process via `pg_terminate_backend` (over the
        direct, non-pooled endpoint, to avoid killing the admin connection
        itself — the first attempt did exactly that, a real gotcha worth
        recording) and the next query succeeded even without
        `pool_pre_ping`: PgBouncer itself absorbed the dead backend and
        silently assigned a new one. Kept the setting anyway — it is
        correct, standard practice, and costs one cheap round-trip per
        checkout — but the specific bug it was reasoned to prevent is not
        currently reproducible against Neon's pooler.
      - `pool_pre_ping`: this one *did* reproduce for real. Opened a pooled
        connection, idled it 8 real minutes (`time.sleep`, not simulated),
        then queried again. Without `pool_pre_ping`: **`OperationalError:
        SSL connection has been closed unexpectedly`** — a genuine failure,
        not a hypothetical one. With it: the same 8-minute idle recovered
        transparently, result correct. This is the one the code comment's
        claim ("Neon drops idle connections") holds up exactly as stated,
        and the setting is the reason a real deployment wouldn't see it.
      No code change — both settings were already correct in
      `app/db/engine.py`; this closes the "untested" half of the earlier
      entry with real, contradictory-in-one-case evidence instead of an
      unverified assumption.
- [x] **The privacy and terms pages no longer carry bracketed placeholders,
      and the consent-record policy version now lives next to the actual
      published policy instead of beside the signup route.** Asked the
      owner first, since neither fact could be invented: the operator name
      to use ("The Morning Mosaic," not a personal name) and the contact
      address for both the grievance officer and general terms questions
      (`gurpreetsinghmattu2002@gmail.com`, the same real inbox already
      configured as `ADMIN_EMAIL`/`SENDER_EMAIL`, rather than a second
      address to maintain).
      - New `config/policy.yaml` (`operator_name`, `version`), validated by
        a new `PolicyConfig` schema and `load_policy()` — same pattern as
        every other `config/*.yaml`. `routes/public.py`'s signup handler
        now records `load_policy().version` on each `Consent` row instead
        of the `CURRENT_POLICY_VERSION` constant that used to sit beside
        it, disconnected from any actual policy text.
      - `/api/config` gained `policy_operator_name`, `policy_version`, and
        `policy_contact_email` — the one place CLAUDE.md already says a
        client learns what's authoritative. `policy_contact_email` reads
        `Settings.admin_email` directly rather than duplicating the address
        into `policy.yaml`: a first version of this change hardcoded the
        same literal string separately into both frontend page files, which
        would have silently drifted from `ADMIN_EMAIL` the first time
        either one changed — caught before committing by checking the
        change against the project's own single-source-of-truth pattern,
        not by a test.
      - `frontend/src/app/privacy` and `.../terms` changed from static
        Server Components to ones that `await serverGet<SiteConfig>(
        "/api/config")` (the same direct-to-backend helper the archive
        pages already used) and render the real operator name, real
        version, and the real grievance/contact email — replacing every
        `[operator name]` / `[date]` / `[grievance officer name]` /
        `[privacy@example.com]` / `[contact@example.com]` placeholder and
        the "pending legal review" banner. A missing/failed fetch falls
        back to a real operator name and the same real address (compiled
        in as a fallback constant) rather than showing a placeholder or a
        blank page.
      - Verified live against the actual running dev servers, not just unit
        tests: restarted the backend, confirmed `/api/config` returns all
        three real values (`"The Morning Mosaic"`, `"2026-09-29"`,
        `"gurpreetsinghmattu2002@gmail.com"`), then fetched `/privacy` and
        `/terms` through the Next.js dev server (which proxies to that
        backend) and read the real rendered HTML and a real `mailto:` link
        on both pages — no bracketed text anywhere.
      - 6 new tests (plus existing `test_config.py`/`test_api.py` assertions
        extended to check `load_policy()`/`policy_contact_email` instead of
        the old constant): `test_config.py` (the version is a real value,
        not the old `"2026-09-01"` placeholder), and new
        `privacy/page.test.tsx` / `terms/page.test.tsx` (real values
        including the contact `mailto:` link render; the fetch-failure
        fallback still shows no placeholder; no bracketed text survives
        anywhere in the rendered output). Also fixed one latent `mypy`
        error in `test_langfuse_recorder.py` from the previous entry — a
        `# type: ignore` comment was on the wrong line and had stopped
        catching the error it was meant to suppress once the call was
        reformatted across two lines — found because this change ran full
        `mypy backend`/`pytest -q` rather than only the files it touched,
        which the previous entry hadn't done. Full suite: 765 backend
        tests (`TEST_DATABASE_URL` set), 36 frontend tests, `ruff`,
        `mypy --strict`, `eslint`, `tsc`, and `next build` all clean.
      Still open, deliberately out of scope here: the actual policy prose
      has not had legal review (CLAUDE.md never claimed it would), and
      `docs/architecture.md`/the incident runbook were not audited for
      other stale references — this closes the specific "bracketed
      placeholder" and "version lives beside the route" gaps the backlog
      named, not a general legal audit.
- [x] **All 87 `config/cities.yaml` coordinates verified against the real
      OpenWeatherMap geocoding API**, not spot-checked or reasoned about.
      One-off script (real `OPENWEATHERMAP_API_KEY` from `.env`, not
      committed): for each city, queried OWM's direct geocoding endpoint
      for `"{name},IN"`, took the candidate closest (great-circle distance)
      to our stored `lat`/`lon` — disambiguating same-named towns in
      different states rather than trusting whichever result OWM ranks
      first — and flagged anything more than 25km off as a real error, not
      a guess. Result: **all 87 within 7.8km of a real OWM match** (the
      worst was Visakhapatnam; most were under 3km), zero flagged, zero
      cities with no OWM result at all. "Adequate for a daily forecast," as
      the file's own header comment already claimed, is now a verified
      fact rather than an assumption. No code or config change — the
      existing coordinates were simply correct.
- [x] **The LLM-dependent evals ran against live models for the first time
      ever, and surfaced a real, reproducible groundedness gap** — see
      `evals/README.md`'s "LLM-dependent tiers: now scored for real" section
      for the full writeup, condensed here. `uv run python -m evals.run` (no
      more gateway blocker): **0 evals skipped**, for the first time.
      `tag_accuracy` (1.00, 9-10/9-10 proposed tags kept across runs) and
      `clustering.full_pipeline` (1.00) score cleanly and consistently.
      `groundedness` does not: **8 live runs scored 0.55, 0.64, 0.67, 0.80,
      0.80, 0.80, 0.80, 0.90** (mean ≈0.75) against a 0.90 threshold —
      7 of 8 runs failed the eval's own bar.
      Root-caused with two follow-up diagnostics (not just measured and left
      alone):
      - A direct `Writer`+`FactChecker` script, re-run several times, showed
        the failures aren't one bug: sometimes 5/5 claims support cleanly;
        one run returned `verification unavailable: JSONDecodeError` on
        *every* claim — the pinned Fact-checker model
        (`@cf/meta/llama-3.3-70b-instruct-fp8-fast`, Cloudflare) occasionally
        returns malformed JSON, and `FactChecker.check()` correctly fails
        closed exactly as designed ("nothing is verified, so every element
        fails rather than passing by default") — this is the safety net
        working, not a hallucination, but it drags the raw score down for a
        reason unrelated to claim quality. Other failures were a genuinely
        defensible but arguably over-strict paraphrase catch (a claim
        flagged because it said "price growth" against a passage that said
        "inflation").
      - A second script ran the *actual* production path
        (`write_and_verify`'s real retry loop, max 2 retries) instead of one
        raw pass, since the eval deliberately measures the latter and
        real delivery never publishes on a raw pass. Across 10 real
        end-to-end attempts (2 fixture stories × 5 rounds): 8 published
        cleanly (several after 1 attempt, some after retries recovered a
        transient failure), but **2 were dropped even after exhausting all
        3 attempts** — a real, measured "quiet news day" rate under today's
        pinned models, not a hypothetical one, and the correct behaviour
        per CLAUDE.md ("if the core headline/summary still fails, drop the
        story") rather than a bug.
      Nothing was changed in response — deciding what to change (Fact-checker
      prompt tolerance for paraphrase, a targeted retry specifically for a
      JSON-decode failure rather than treating it the same as a real
      unsupported claim, or pinning a different model) is a real decision
      with real trade-offs, not something to guess at in the same pass that
      found the gap. Recorded as a still-open item above rather than closed,
      since the underlying groundedness shortfall is real and unresolved —
      only "run the eval and find out" is done.
