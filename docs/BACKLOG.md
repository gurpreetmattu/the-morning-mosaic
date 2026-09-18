# Backlog

Running list of what is pending, what is provisional, and what is known to be
broken. Kept in the repo so it survives between sessions.

**Convention:** update this file at the end of every step, in the same commit
as the work. Move finished items to "Done" with the commit that closed them.
Add anything discovered mid-task rather than leaving it in a chat message.

- **Last updated:** 2026-09-18, at commit `993f19b`
- **State:** 111 commits · 82 backend modules, 16 eval modules, 27 frontend files, 15 Terraform
  files, 2 Dockerfiles, 3 GitHub Actions workflows, 2 ADRs, an architecture doc, and an incident
  runbook · 654 Python tests (625 backend + 29 evals, three migrations now verified against a real
  throwaway database, seven of which actually launch every scheduled job as a subprocess — see
  the critical fix in Done, three of which race real concurrent database connections against each
  other, thirty of which cover the weekend edition's selection logic and its build/delivery
  wiring — see the weekend-content entry in Done, seven of which cover "AI tool of the day" —
  see its own Done entry, six of which cover the two real LangGraph graphs the build and
  late-update jobs now run on — see the langgraph-pipeline entry in Done, six of which catch
  a real Turnstile bug a blank-but-present `TURNSTILE_SECRET_KEY=` caused — see the
  llm-gateway-groq entry in Done, and eleven of which cover a source's malformed feed dates and
  an unbounded cluster size, both found by actually running the pipeline against real, live
  sources — see the source-terms-review entry in Done), 31 frontend tests
  (8 pure-logic + 23 new component/interaction tests under jsdom and React Testing Library — see
  the component-tests entry in Done) ·
  ruff, `mypy --strict`, eslint, prettier, tsc, `terraform fmt`, and `actionlint` all clean
  (`terraform validate` needs `terraform init`'s cached providers, not available in this
  environment) · **7 scheduled jobs** — see the purge-job entry in Done · the real Neon database
  now has the full schema and reference data (87 cities, 27 sources, all disabled) — see the
  accounts-provisioned entry in Done

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
- [ ] **No Langfuse tracing** wired, though it is a dependency and in the spec.
- [x] ~~Planted-error catch rate is measured by hand, not by an eval.~~ Now
      `evals/fact_checker_catch_rate.py`: 10 deterministic cases (control +
      4 error categories, across 2 base stories) pass today at 100%; the
      other 3 categories (invented prose fact, reversed meaning, unstated
      causation) are built and ready but need a live model to actually
      score — see `evals/README.md`.
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
- [ ] **Section HTML has never been seen in a real mail client.** It is built
      to the email-safe rules (inline styles, no classes, no flexbox) and tests
      assert those, but CLAUDE.md requires checking Gmail web and mobile plus
      Outlook. Nothing has been sent anywhere.
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

**Agents** (7 of 10 done — Orchestrator, Collector, Ranker, Writer,
Fact-checker, Delivery, Feedback. This line previously said "5 of 10" and
listed Delivery and Feedback as not done — stale since those two jobs were
built; caught by an audit of this file against the code, not by anyone
noticing the count was wrong.)
- [ ] Image finder (6) · [ ] Weather (7)
- [~] Layout (8) — sections, per-user selection, full email assembly, and
      PDF pages (genre pages once per revision, merged per reader on first
      download) are done. Still to do: the extras the masthead leaves room
      for (weather box is wired but has no Weather agent feeding it; market
      strip, quiz, quote and "On this day" are not built).

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
- [ ] Prompt for the Image finder (`ranker_v1`, `writer_v1` and
      `fact_checker_v1` are written; the Orchestrator needs none)

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
- [ ] weather · [ ] markets · [ ] sports · [ ] releases · [ ] deals
- [ ] images · [ ] quotes / "On this day"
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
      `PENDING`.
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
