# Backlog

Running list of what is pending, what is provisional, and what is known to be
broken. Kept in the repo so it survives between sessions.

**Convention:** update this file at the end of every step, in the same commit
as the work. Move finished items to "Done" with the commit that closed them.
Add anything discovered mid-task rather than leaving it in a chat message.

- **Last updated:** 2026-09-17, at commit `PENDING`
- **State:** 81 commits · 78 backend modules, 16 eval modules, 22 frontend files, 15 Terraform
  files, 2 Dockerfiles, 3 GitHub Actions workflows, 2 ADRs, an architecture doc, and an incident
  runbook · 556 Python tests (527 backend + 29 evals, one of which now runs the real Alembic
  chain against a throwaway database, and seven of which actually launch every scheduled job as
  a subprocess — see the critical fix in Done), 8 frontend tests (all green, database included) ·
  ruff, `mypy --strict`, eslint, prettier, tsc, `terraform fmt`, and `actionlint` all clean
  (`terraform validate` needs `terraform init`'s cached providers, not available in this
  environment) · **7 scheduled jobs now** (was 6) — see the purge-job entry in Done

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
- [ ] **Conflicting key facts are not detected.** The rule is "state that
      reports differ, or drop". Nothing compares figures or claims across the
      articles in a cluster yet. Probably belongs with the Fact-checker, but it
      has no owner today.
- [ ] **The deterministic clustering fallback measurably misses paraphrased
      duplicates.** `evals/clustering.py`'s title-baseline eval scores it at
      80% pairwise accuracy on a small labelled fixture: it correctly never
      invents a false merge, but the two genuinely-duplicate pairs, whose
      headlines were paraphrased rather than near-identical, don't clear
      the 0.5 Jaccard-similarity threshold and stay unmerged. Only reachable
      when the LLM clustering step itself fails and this fallback takes
      over, but that's exactly when it matters most.
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
- [ ] **The corrections process CLAUDE.md specifies doesn't exist at all,
      not just in the archive.** Nothing writes a `Correction` row, nothing
      renders one in the archive, and there's no template or job step for
      "a correction note appears in the next edition for users who
      received it." `docs/runbooks/incident-response.md`'s "story already
      reached readers" case documents a manual workaround (a hand-written
      SQL insert and a manually-sent note) for exactly this reason.
- [ ] **Turnstile has a real widget now but no real site key to test it
      against.** `TurnstileWidget` renders nothing without
      `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, matching the backend's own "skip
      outside prod" behaviour — so signup works end to end in dev, but the
      actual challenge flow has never run.
- [ ] **The frontend has no component or interaction tests.** `frontend/src/lib/api.test.ts`
      (8 tests) covers only the CSRF cookie-parsing and error-formatting
      logic; signup, the preferences dashboard, and the admin dashboard
      have zero automated coverage of rendering or interaction — only the
      manual, one-off Docker smoke test done while reviewing the frontend
      build. A form field silently breaking would only be caught by
      someone clicking through it.
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
- [ ] LangGraph build graph · [ ] late-update graph. The Orchestrator runs the
      per-genre pipeline as plain code today; CLAUDE.md specifies LangGraph.
      Decide whether to wrap it or amend the spec.
- [ ] **Bounce parsing has never seen a real Gmail DSN.** The parser is built
      to RFC 3464 and tested against synthetic reports; `ImapBounceSource` has
      never spoken to an actual IMAP server. Both need a live check once the
      Gmail app password exists.
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
- [ ] **The weekend edition has no content behind it, only a flag.**
      `is_weekend` is computed (`Edition.is_weekend`, weekday >= 5) and
      threaded through late update, but nothing reads it: CLAUDE.md's
      Saturday "longer reads" (extended summaries of the week's most
      significant verified stories) and Sunday "weekly recap" (built from
      stories already verified Mon–Sat) need their own selection logic —
      querying the week's published stories and choosing/extending
      them — that doesn't exist anywhere yet, template or otherwise.
- [x] PDF assembly and caching — `LocalObjectStorage` in dev, `GcsObjectStorage`
      behind the same interface for prod (untested against a real bucket)
- [ ] Bounce handling over IMAP

**Services**
- [ ] weather · [ ] markets · [ ] sports · [ ] releases · [ ] deals
- [ ] images · [ ] quotes / "On this day"
- [ ] **"AI tool of the day" has no code**, distinct from the external-API
      services above: CLAUDE.md says it's "picked from tools covered in
      that day's verified AI stories," so it needs no new provider account
      — just logic to select one from that day's Writer/Fact-checker
      output, which doesn't exist yet.

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
