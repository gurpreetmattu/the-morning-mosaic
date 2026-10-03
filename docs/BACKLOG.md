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

- [ ] **LAUNCH BLOCKER: free-tier LLM capacity cannot carry one daily build
      (measured 2026-10-01).** First real prod build (edition 2026-10-01, 16 min)
      produced 4 stories; 8 of 10 genres fell to "quiet news day". Cause, from
      `llm_calls`: Fact-checker's Cloudflare route returned HTTP 429 "used up your
      daily free allocation of 10,000 neurons" on 411 calls, its Groq
      `gpt-oss-20b` route 429'd on 318 more, and the Writer's Gemini flash-lite
      route 429'd on 211 of 354 calls; the Ranker hit both Groq and Gemini
      limits. The fail-closed design did exactly what it should (nothing
      unverified published), but the yield is unusable. A single build also
      spends the next build's quota: Cloudflare's allowance resets 00:00 UTC
      (05:30 IST), AFTER the 04:15 IST build, so the next build starts with the
      previous day's quota already gone. Needs an owner decision: a paid tier
      (Groq pay-as-you-go is the cheapest route; a full day should cost
      pennies - measure it), or cut the per-day call volume. Do NOT open signups
      until a build yields 4-6 verified stories per genre.
      **Owner constraint (2026-10-01): spend nothing on LLMs (student).** So the
      launch scope is cut to 5 genres (india, business, technology, ai, sports),
      pool 6 each - see the launch-scope Done entry. Still open under this
      constraint: re-route Writer/Fact-checker across Groq's three free
      per-model buckets (200K tokens/day each; `config/models.yaml`, needs a
      small eval run), pause the late updates, and measure one clean build.
      Cerebras was ruled out: its free tier is $5 of credit that needs a payment
      method and expires in 30 days.
      **First unattended night (2026-10-02, 5 genres):** pipeline works end to end -
      scheduler fired every job on time, build 04:15-04:20 (4.5 min), late updates 05:35 and
      07:05 each published a better revision, 7 delivery runs, and the 09:05 failure notice
      reached the test subscriber because both their genres (india, business) were empty
      ("all genres failed -> failure notice" path verified for real). Yield: rev 3 = ai 5,
      technology 4, sports 2, india 0, business 0. Evidence from `app.buildreport`:
      Cloudflare returned 0 successful calls all night (369 "daily free allocation of 10,000
      neurons" errors) and STILL did at 14:23 IST, long after its documented 00:00 UTC reset,
      so it cannot be relied on as the pinned Fact-checker route; the fallback gpt-oss-20b did
      35 ok calls and 287 429s (8K tokens/min, reasoning-heavy output ~1.6K tokens/call);
      Writer's Gemini route 115 quota 429s; Ranker 55 Groq 429s + 18 invalid-JSON. Collection
      itself is healthy (india 40 fresh articles / 6 sources, business 40 / 4). Hypothesis,
      NOT confirmed: india/business (strict corroboration) lose when Ranker's LLM clustering
      fails and the title-only fallback splits same-event articles into single-source
      clusters. Per-genre drop reasons are not logged anywhere, which is why this is still a
      guess - add them to `pipeline_runs.detail` (collected, clusters, pooled, dropped by
      reason, attempted, verified, dropped-after-retries) before changing any model.
      The late updates paid for themselves (they added 6 stories), so do not pause them.
      **Measured cost (2026-10-01, from `llm_calls` + provider pricing pages):**
      earlier clean runs cost ~14.5k input / 2.1k output tokens and ~$0.010 per
      persisted story, so 50-100 stories/day is ~$0.5-1.0/day for a build, ~$0.8-1.6/day
      with late updates and a 60% safety margin (~$25-49/month). Today's two
      incomplete runs billed ~$0.60 for 4 stories (wasted attempts). Prices used
      ($/1M in/out): gpt-oss-20b 0.075/0.30, gpt-oss-120b 0.15/0.60, qwen3.8-27b
      0.80/4.00, Cloudflare llama-3.3-70b 0.293/2.253, Gemini Flash-Lite 0.30/2.50.
      Caveats: small sample (24 stories from limited-genre runs), Gemini price
      assumed equal to the page's Flash-Lite listing, and failed 429 calls are
      unbilled. The constraint is rate limits and quotas, not price.
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
- [x] ~~No git remote.~~ Pushed 2026-10-01 to a private GitHub repo
      (`gurpreetmattu/the-morning-mosaic`) after a secrets/history audit found
      nothing leaked. CI ran on GitHub for the first time the same day and
      failed on three things, all found by reproducing from a fresh clone
      and fixed: 10 unformatted files (`ruff format --check`), `tsc` needing
      `next typegen` for `LayoutProps` on a clean checkout, and a theme-toggle
      e2e that raced the 200 ms background transition. All 6 jobs now pass
      (`36848457172`). Still open: the Lighthouse job passed once but stays
      `continue-on-error` until a few runs show stable numbers; Actions warns
      that `checkout@v4`/`setup-node@v4`/`setup-uv@v5` run on a deprecated
      Node 20 runtime - bump them before it is removed.
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
- [x] ~~`app/config/loader.py` finds `/config` by walking up from its own
      file, which only lands on the repo root in an editable dev
      checkout.~~ Confirmed by actually building and running the backend
      image: installed into site-packages, the same walk lands inside
      `.venv/lib/python3.12/`, not the repo. Fixed with the existing
      `CONFIG_DIR` override — `backend/Dockerfile` sets it to `/app/config`
      and copies `/config` there — rather than changing the loader, since
      the override already existed for exactly this.
- [ ] **Section HTML sent for real; Gmail web now visually confirmed,
      Gmail mobile and Outlook still open.** Added the owner's address to
      `TEST_EMAIL_ALLOWLIST` and sent one full multi-genre edition through
      the real path (`EmailRenderer` -> `Sender` -> actual Gmail SMTP, not a
      mock) — `Sender.send()` returned `outcome=sent` with a real
      `Message-ID`. **Gmail web now actually checked, not just sent**
      (2026-09-30, via a real connected browser, not a screenshot handed
      over for guessing): opened the live message and scrolled the full
      edition — masthead, market strip, "On this day", "Today in 60
      seconds", every genre section with its "Sources:"/"Source:" links and
      "Why this matters" block, the Gaming section's real hotlinked Pexels
      image (loaded with no "images blocked" bar, confirming Gmail trusts
      the sender enough to auto-display — with its "Photo by ... on Pexels"
      credit) and its "Deals:" callout, and the footer's "Download today's
      edition as a PDF" / "Manage your preferences" / unsubscribe links —
      all rendered correctly, nothing broken or unstyled. What's still open
      is Gmail mobile and Outlook specifically — CLAUDE.md names all three,
      and Outlook in particular is the one most likely to choke on
      anything Gmail web's more forgiving renderer let slide (Outlook's
      Word-based engine is far stricter about flexbox/CSS than Gmail) —
      that still needs either a real Outlook mail client/account or a
      screenshot service, neither available this session.
- [ ] **Turnstile has never been exercised against Cloudflare.** Without a
      secret configured the check is skipped outside prod and raises in prod,
      and the verify call itself is covered only by its own error paths. It
      needs one real token round trip once the account exists.
- [ ] **Turnstile has a real widget now but no real site key to test it
      against.** `TurnstileWidget` renders nothing without
      `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, matching the backend's own "skip
      outside prod" behaviour — so signup works end to end in dev, but the
      actual challenge flow has never run.
- [x] ~~The frontend has no component or interaction tests.~~ See the
      component-tests Done entry.
- [x] ~~**Terraform does not pass `DATABASE_DIRECT_URL`, `LLM_SECONDARY_URL` or
      `LLM_SECONDARY_API_KEY` to Cloud Run, and has no Secret Manager
      container for the two secrets**~~ (found by `app.preflight`, 2026-10-01;
      fixed the same day in `infra/locals.tf`, `infra/secrets.tf`,
      `variables.tf`; `terraform validate`/`fmt` pass, `apply` still never
      run). Before the fix, in prod that meant the job lock
      runs on the pooled Neon URL (the advisory-lock hazard in
      `app/jobs/locking.py`) and the Fact-checker's Cloudflare gateway is
      unconfigured, so its only route was Groq's quota. **New obligation:**
      populate `database-direct-url` (and `llm-secondary-api-key`) in Secret
      Manager, and set `llm_secondary_url`, before the first apply.

- [ ] **PLANNED 2026-10-02 (agreed with the owner): turn on auto-deploy from GitHub.**
      `deploy.yml` is the GitHub -> Cloud Run path (build both images, push, terraform
      apply) but is gated off: no `GCP_PROJECT_ID` repo variable and no Workload Identity
      Federation. Steps: (1) fix the `BASE_URL`/tfvars bug below first; (2) create the WIF
      pool + provider + deploy service account bound to `gurpreetmattu/the-morning-mosaic`
      (IAM changes - needs the owner's approval); (3) set the repo variables
      (`GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`,
      `TURNSTILE_SITE_KEY`, `LLM_SECONDARY_URL`, `SENDER_EMAIL`, `ADMIN_EMAIL`,
      `LLM_GATEWAY_URL`, and a `BASE_URL`); (4) test on a throwaway change. Not Cloud Run's
      built-in 'deploy from GitHub': Terraform owns the services/jobs, and there are two
      images, 7 jobs and a build-time Turnstile arg. Do this AFTER reading the first real
      build with the 5-genre scope.
- [x] ~~Pending owner action: apply `infra/release.tfplan`~~ Applied 2026-10-01 ~20:15 IST (by
      Claude on the owner's instruction). Live: 5 genres on `/api/config`, landing says
      "Five genres", disabled genres refused at signup; services on `328e625`; job timeouts
      build 5400 / late-update 1500 / delivery 1800 / failure-notice 1800. Lesson: the first
      attempt hit a DNS blip, left a stale GCS state lock, and every later Terraform command
      would have failed until it was cleared. With the GCS backend `terraform force-unlock`
      wants the lock OBJECT'S NUMERIC GENERATION (`gcloud storage objects describe
      gs://the-morning-mosaic-tfstate/default.tflock --format='value(generation)'`), not the
      UUID in the lock file.
- [ ] **`deploy.yml`'s terraform apply has no `terraform.tfvars` in CI**
      (`*.tfvars` is gitignored), so it does not repeat `base_url`, despite its
      own comment saying it repeats what's in tfvars/state. Every CI deploy would
      reset `BASE_URL` to the variables.tf placeholder and break every email
      link. Found 2026-10-01 while wiring the Turnstile key; not fixed (needs a
      decision on a `BASE_URL` repository variable vs a committed non-secret
      tfvars file). Same applies to any other tfvars-only value. Until fixed,
      deploy by hand with `terraform apply` locally.

## 3. Provisional values that will cause harm if forgotten

- [ ] **`launch_date: 2026-10-01`** in `config/editions.yaml` is still a
      placeholder, and edition numbering derives from it — only set the real
      value when actually going live. *3 days away as of 2026-09-28.* Local
      testing no longer needs to touch this file to get past it: see the
      `EDITION_LAUNCH_DATE_OVERRIDE` entry in Done.
- [ ] **The groundedness gap is partly fixed (malformed-JSON retry, see its
      own Done entry) but not closed — now root-caused further, not just
      re-measured (2026-09-30).** Re-ran `uv run python -m evals.run`
      several times once the calendar day turned over: the very first run
      scored 0.80 with no quota errors at all (a real, non-catastrophic
      result), and a follow-up diagnostic script (prints every claim's
      verdict, not just the pass count) caught the *specific* failure live:
      "keep inflation within" vs. "maintain inflation inside" and "cleared"
      vs. "approved" both marked `PARTIAL` — the exact same paraphrase-
      strictness pattern already on record, reproduced under a clean quota,
      not a new bug.
      Then, from repeating that diagnostic several more times back to back,
      **personally re-exhausted both providers the Fact-checker depends
      on**, not just Groq this time: Cloudflare's free "10,000 neurons/day"
      allocation on `@cf/meta/llama-3.3-70b-instruct-fp8-fast` (the pinned
      secondary) and Groq's `openai/gpt-oss-20b` daily token quota (used up
      to 199,7xx/200,000 again) both returned HTTP 429 in the same runs —
      confirmed from the raw `LlmHttpError` text on both, not inferred.
      With neither route available, `FactChecker.check()` correctly failed
      closed on every claim (`LlmUnavailableError`), which is why several
      runs in the same session scored 0.00–0.60: **that is the fail-closed
      design working exactly as intended, not a Writer/Fact-checker
      defect** — confirmed this time, not left as an open "undetermined"
      the way the 2026-09-29 catastrophic scores were. The two previous
      unattributed 0.00/0.18 scores are now far more likely to have been
      this same cause, though that specific day's raw error text was never
      captured to confirm it retroactively.
      What's still genuinely open: whether the paraphrase-strictness false
      positive is worth tightening the Fact-checker's prompt or tolerance
      for, a real product decision with trade-offs, left to the owner (see
      `evals/README.md`). What's now closed as a question: there is no
      remaining "is this a real quality regression" mystery — every
      substantive score has a confirmed cause, either paraphrase-strictness
      or quota exhaustion.
- [ ] **Free-tier fragility.** During verification OVH rate-limited into a
      circuit-open state, Pollinations began returning 402, and four ids in the
      gateway's own catalogue 404'd or 401'd. A vanished pinned model stops the
      build rather than degrading it — correct, but it will happen.
      **Personally hit, not just anticipated, on 2026-09-29:** repeated live
      eval runs (see the groundedness Done entries) exhausted Groq's real
      daily token quota (`openai/gpt-oss-20b`: 199,714/200,000 TPD used) —
      confirmed via the raw `LlmHttpError` text, not inferred. This is
      exactly the Fact-checker's own `availability_fallback_model`, so once
      Cloudflare *also* has a bad moment, verification has nowhere left to
      go until the quota resets. One real, load-bearing implication: a day
      of heavy manual eval/diagnostic runs against live models can burn
      the same quota real subscriber traffic needs — worth keeping in mind
      before running many live evals back-to-back close to a real send.
      **Happened again the very next day it was possible to (2026-09-30),
      this time both routes at once:** re-running the groundedness eval
      several times to root-cause the previous day's catastrophic scores
      burned through Cloudflare's separate "10,000 neurons/day" free
      allocation *and* re-hit Groq's daily TPD cap in the same sitting —
      not a new kind of fragility, but confirmation that recovery from one
      exhausted provider is not "wait a day," it is "wait a day per
      provider, and don't spend that day's fresh quota re-running the same
      diagnostic against both of them." A live groundedness measurement
      needs to be one deliberate, small batch (2–3 runs), not an open-ended
      diagnostic loop, until a paid tier or a wider fallback chain exists.

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
- [x] ~~Late update: re-collection of breaking stories and publishing a new
      revision~~ Built long ago (`f032aa0`, see the late-update-job Done
      entry) and left unchecked here since — the same staleness pattern
      caught elsewhere in this file (bounce handling, the agent count),
      always by auditing against the code rather than anyone noticing.
      `app/jobs/late_update.py` exists, has its own docstring describing
      exactly this, and 14 tests in `test_late_update_job.py`.
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
- [x] ~~Bounce handling over IMAP~~ Built long ago (`79726bd`) and left
      unchecked here since — caught by the same kind of audit-against-the-
      code that has caught this file's staleness before. See the real-Gmail-
      DSN Done entry for the live verification this line was actually
      waiting on.

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
- [x] ~~**`terraform plan`/`apply` have never run against a real project.**~~ Applied 2026-10-01; see the first-deploy Done entry. Original note:
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
- [x] ~~Monitoring covers two conditions, not the four CLAUDE.md lists.~~
      See the monitoring-signals Done entry: all four now have a real alert
      policy. `terraform apply` still hasn't run against a real project
      (Blockers), so none of the four has fired for real yet — that's the
      same open gap the other two already had, not a new one.
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

### Website redesign — DESIGN.md "Retro Broadsheet"

Steps 1–2 of DESIGN.md §21 are done (see Done). Remaining, in order:
- [~] **3. Landing page** built (route groups `(landing)` / `(site)`; sections per
      §9.1). Still open on it: the annotated anatomy diagram (currently a
      numbered list), the "Sample edition" CTA and nav link (`/sample` does not
      exist, so the secondary CTA is "See what's inside" and the nav omits
      Sample / How we report), masthead reveal + section entrance motion (§10),
      market strip "print in", the PDF tab on the preview, the weekend/PDF
      cards' art, Playwright screenshots at 360/390px (the browser tool cannot
      shrink below ~1280px, so phone width is unverified), and `?genres=` is
      written by the stamp sheet but not yet read by `/signup`.
- [~] **4. Subscribe flow** built at `/subscribe` (`/signup` 308-redirects, query kept):
      4 ticket steps, ARIA city combobox, 30-minute time stubs, frequency,
      edition preference, keywords, name/email, 18+ and an explicit consent
      checkbox, live "Your edition" panel, stamped checkboxes, check-your-inbox
      screen. Only non-personal choices go to sessionStorage. Still open:
      the explicit consent checkbox is UI-only (the payload/API is unchanged,
      the backend records consent at signup as before) - confirm with the
      owner whether the API should also require it; no resend-link or
      `/subscribe/check-email` route (result renders in place; no resend
      endpoint exists); the time readout has no split-flap animation;
      `?step=` in the URL is not used (Back/refresh keep entries via
      sessionStorage but always restart at step 1); Playwright check of the
      sticky mobile Next bar at 360px.
- [~] **5. Remaining pages** built: `/editions` (was `/archive`, redirects for both
      routes, month-grouped), `/sample` (printable), `/how-we-report`,
      404 and error pages, preferences restyled with the shared subscribe
      controls, and the backend's emailed-link pages (`backend/app/api/pages.py`:
      opt-in, unsubscribe, feedback, login, admin login) restyled in the same
      paper-and-ink look. DESIGN.md's Next `/confirm/[token]` and
      `/unsubscribe/[token]` were deliberately NOT built: those links are
      served by the backend so GET stays state-free and the CSP stays
      `default-src 'none'`. Still open on step 5:
      - `pages.py` colours are copied from tokens.json; generate them instead.
      - The DB-backed API tests (41 skipped locally: no `TEST_DATABASE_URL`)
        were NOT run against the restyled pages; the two HTML assertions in
        `test_api.py` (`method="post"`, no `<script`) were verified by hand.
      - `/feedback` general feedback form (DESIGN.md 9.11) - needs a new
        backend endpoint; not built. Not in CLAUDE.md's product decisions.
      - `/status` still shows only degraded/ok (DESIGN.md wants scheduled /
        sending / sent / delayed / not sent; the API has no such state).
      - Admin, privacy, terms and status pages keep their old markup and are
        not prettier-clean at HEAD; they use the bridge tokens.
      - The archive edition page renders the email section HTML as-is, so
        story blocks there keep the old email styling until step 6.
      - Sources are not listed by name on How we report (no API for them).
- [~] **6. Email + PDF parity** built. `frontend/design/tokens.json` is now the
      single source for the site AND the backend: `npm run tokens:backend`
      writes `backend/app/render/palette.json` and the `theme:` blocks in
      `config/genres.yaml`; CI runs `tokens:backend:check` and a
      `test_design_sync.py` guard fails if the two drift. The email is 600px
      with a dateline strip, nameplate (Georgia; web fonts don't load in mail),
      "Curated for" and weather boxes, spot-ink section bands, slip-style
      extras; archive sections, the two system notices and the PDF cover/pages
      share it. Tagline in email + PDF is now "The morning paper, set to your
      interests." Still open on step 6:
      - **Real-client check, partly done.** A test edition (synthetic content, subject
        prefixed `[TEST - sample content]`) was sent through the real `Sender` to the
        allowlisted inbox and viewed in **Gmail web (desktop Chrome)** on 2026-09-30:
        paper background, 600px card, dateline, boxed Curated-for/weather, quote frame,
        market strip, spot-ink section bands, hedged-story note, Why-this-matters rule,
        dotted separators, weekend recap/quiz, correction note and footer links all
        rendered as designed. Gmail **strips the nameplate's red text-shadow** (it shows
        plain black ink - acceptable). Not yet seen: the "Stop press" 60-second box in
        Gmail, **Gmail mobile, Outlook (desktop/web), and Gmail's automatic dark mode.**
      - **PDF theme fixed (2026-10-03).** The PDF used a forced white page and a
        plain cover, nothing like the email. Pages now use the email's paper tint
        and the cover has the email masthead (dateline, red-shadow nameplate,
        double rule, boxed "Curated for"). Rendered for real in the backend image
        and checked. Still open: no weather box on the cover, and white-paper
        print-friendliness was traded away for matching the email.
        Follow-up: stories were unsplittable at screen-size type, leaving pages a
        third empty; print CSS now shrinks type and lets stories break, and the
        cover lists genres with page numbers.
        **Then (2026-10-03):** the last page of every genre was still half blank
        because each genre was its own PDF, merged afterwards. A reader's PDF is
        now ONE document, so genres flow on from one another and the cover's page
        numbers come from WeasyPrint's `target-counter`. Trade-off: the per-genre
        render cache is gone, so a reader's first download lays out their whole
        edition (cached per reader after that).
      - No dark-mode variant for email (would need a `<style>` block; the
        section HTML forbids one) - clients that auto-invert get explicit
        backgrounds on every container.
      - No stamp / halftone PNGs in email (DESIGN.md 17): the masthead has no
        SAMPLE-style stamp images and sections have no halftone band; both need
        hosted images.
      - `pages.py` (emailed-link pages) still copies its colours by hand.
      - Weekend/longer-read block headings use ink, not a genre ink.
- [~] **7. QA** built (`frontend/tests/e2e`, `npx playwright test`; runs a production
      build against a mock API, drives installed Chrome locally and Playwright
      Chromium in CI - new `e2e` job in `ci.yml`, first CI run not yet seen).
      168 tests: every route x 5 viewports (360/390/768/1280/1536) x Morning +
      Late (loads, no horizontal overflow, clean console, no request to another
      origin, no unexpected HTTP error); axe (WCAG 2.2 AA tags, zero
      serious/critical) on every route, phone + desktop, both themes; the
      subscribe flow end to end and its validation, refresh and sticky mobile
      bar at 360px; reduced motion, forced colours, theme toggle persistence,
      skip link, one h1 per page, signed-in preferences; landing budgets
      (JS 151 KB gz of 180, fonts 172 KB of 200, CLS 0.02 of 0.05, LCP 0.3 s
      unthrottled). What it caught and fixed: no h1 on /subscribe, faded stamp
      numerals failing contrast, fonts 246 KB over budget (Special Elite
      dropped). Still open on step 7:
      - **Lighthouse (mobile, simulated 4G, `npx lighthouse`) was run by hand**
        on the landing page against a local production build. Final state, 4
        runs on an idle machine: LCP 1.7-1.9 s, CLS 0, TBT 200-310 ms,
        performance 92-96. Getting there: it first found a 0.145 layout shift
        (font swap), which `next/font/local` metric-matched fallbacks fixed;
        preloading fonts then hurt LCP (removed); `content-visibility: auto`
        on far sections cut layout cost; a fixed two-line nameplate removed a
        desktop-only 0.22 shift; and `experimental.inlineCss` (see below)
        removed the render-blocking CSS round trip. Results are noisy when
        the machine is busy (TBT 350-1,990 ms in runs taken right after the
        test suite) - measure on an idle machine. INP is not measured by
        Lighthouse. Now automated: `npm run perf:lighthouse` (median of 3, fails on
        LCP > 2.5 s, CLS > 0.05, TBT > 600 ms or score < 80) and a `lighthouse`
        CI job - which is `continue-on-error` until it has run on GitHub and
        its numbers are known to be stable; then make it blocking. `experimental.inlineCss` is an
        experimental Next flag: re-check it on every Next upgrade. Its cost:
        the HTML document grew from 12.5 KB to 44 KB compressed (the CSS is
        embedded twice, in the HTML and in Next's client payload); total page
        weight is 442 KiB including 172 KiB of fonts, inside the budget.
      - **No committed screenshot baselines** (Windows/Linux font rendering
        differs); screenshots are written to `test-results/` and uploaded by CI.
      - **Not covered:** the admin page, a screen-reader (NVDA/VoiceOver) pass,
        the archive page against a real (non-mock) section HTML, and the
        signup form typed-before-hydration case. (Now covered: a 320px viewport
        on every route, which is what 400% zoom reflows to, and a keyboard-only
        pass that checks every tab stop on 7 pages has a visible focus
        indicator; the suite runs the standalone server the Docker image uses.)
- [ ] Politics motif: DESIGN.md's "stars and stripes" is US-flag imagery; use a
      neutral campaign-button/ballot motif instead.
- [x] Genre period motifs (§6.2) - ten CSS-mask SVG strips (each under 400 bytes) on
      the stamp cards and the `/sample` section titles; and the first-visit
      masthead reveal (§10 #1 typewriter dateline, #2 letter-by-letter
      nameplate + drawn rule, #5 preview unfold) as pure CSS - no GSAP added -
      gated to the first landing visit per session and collapsed under
      reduced motion. Later also built: §10 #7 split-flap time readout (only
      changed characters flip; the sentence for assistive tech is separate) and
      #10 step-change slide. Not built from §10: #3 section entrances (would
      hide content from screenshots/axe until scrolled), #6 market "tape
      prints in" (the only market strip is in the email/sample), #11 confirm
      stamp (deliberately: the check-your-inbox screen appears BEFORE the
      reader confirms, so a "subscribed" stamp there would be untrue; belongs on
      the backend's opt-in success page if wanted), and #13 theme cross-fade
      is only the 200 ms body background transition. Also: the Politics motif
      is campaign buttons, not the "stars and stripes" DESIGN.md suggested.
- [ ] Legacy Tailwind bridge names in `globals.css` (`surface`, `muted`, `rule`,
      `accent`, `accent-soft`, `background`, `foreground`) — remove as pages
      are rebuilt.
- [ ] `npm run tokens` runs on predev/prebuild; add it to CI before `tsc`
      (generated `src/styles/tokens.css` is committed so CI works without it).
- [ ] Dev note: the site must be opened at `localhost`, not `127.0.0.1`
      (Next dev blocks client scripts from other origins; `allowedDevOrigins`).

## 5. Environment

- [x] ~~WeasyPrint cannot run on this machine~~ It can't, but
      `backend/Dockerfile` installs the GTK/Pango/Cairo libraries it needs,
      and `weasyprint_renderer` was verified for real inside the built
      image: `HTML(string=...).write_pdf()` produces genuine PDF bytes.
      Fixed one real bug in the process — the runtime user's `$HOME` wasn't
      writable, so fontconfig couldn't cache, which the image now sets to
      `/tmp`.
      **The "actual layout of a real section" half, closed separately and
      later (2026-09-29):** built the real image, pulled a real, already-
      published, already-rendered `EditionSection.html` straight out of the
      database (gaming, 2026-10-15 — chosen because it's the one with the
      most extras: a real hotlinked image plus a real "Deals:" callout),
      and ran it through the actual `page_html()` + `weasyprint_renderer()`
      path inside the container — not a trivial string. Real, genuinely
      viewable result: a 3-page A4 PDF with the correct genre theme color
      on the heading, the real Pexels image successfully fetched over the
      network and embedded (confirms hotlinked images actually resolve at
      PDF-render time, not just in an HTML email client), the real game
      deals with correct names/discounts/store links, and every story's
      real headline/summary/source link, all correctly styled. One real,
      minor thing this caught that a trivial-string test never could: a
      story's body text and its "Source:" line landed on opposite sides of
      the page 1/2 break — not broken, just an unpolished pagination
      choice (no `break-inside: avoid` on a story block), left as a
      genuine small gap rather than fixed on the spot, since it's cosmetic
      and this task was about verifying the layout renders, not redesigning
      it.
- [ ] **`GcsObjectStorage` has never touched real Cloud Storage.** No GCP
      project exists yet (see Blockers). It mirrors `LocalObjectStorage`'s
      interface exactly, so the PDF route needs no change once a bucket
      does exist; the object-key layout (`pdf/readers/{revision}/{user}.pdf`;
      the per-genre `pdf/sections/...` keys were retired 2026-10-03) is what the 30-day lifecycle
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

- [x] **First untouched-quota night with every fix live (2026-10-03).** Build 04:15-04:21
      (5.6 min), late updates 05:35 and 07:05 (4.6/4.8 min), delivery 07:00 sent 1 (revision 2;
      revision 3 appeared 07:10, after the slot). Revision 3 = ai 7, india 6, sports 9,
      technology 7, business 0 (quiet). Cloudflare did 109 fact-check calls with ZERO failures
      (fresh quota), Gemini 29 quota 429s, Ranker 29 Groq 429s + 31 invalid-JSON answers;
      paid-plan price of the whole day would have been $0.40. So the free tiers CAN carry the
      5-genre scope when nothing else spends their quota. Business stays empty with model
      clustering working: 69 of 71 clusters are single-outlet (strict corroboration) and the two
      pooled stories died at the Writer - a SOURCES problem (4 outlets, 20 of 80 items too old).
- [ ] **Findings from the first Saturday/weekend email in Gmail (2026-10-03), worst first.**
      Verified working live: the quiet-day note ("Business & Markets: A quiet news day..."),
      one-number weather, no duplicate stories between sections, Today in 60 seconds, scores and
      fixtures, images with credits, footer links, longer reads and quiz blocks render.
      1. [FIXED 2026-10-03, owner decision] **The weekend quiz can print wrong answers** (the
         distractors were other true stories from the same week). Switched OFF: `quiz` removed
         from both weekend lists in `config/editions.yaml`, and `load_weekend_features` now
         ignores any stored feature the config has turned off, so the Saturday row already in
         the database can never be sent. To bring it back, redesign so the answer AND every
         distractor are verifiable from the data (e.g. 'which outlet reported X' against outlets
         that did not cite it, or a number from a verified sentence with off-by-N distractors),
         print genre names properly ('in AI'), and cover the same-event-two-headlines case.
      2. [FIXED 2026-10-03] **'AI tool of the day' was a Sling TV story.** `ai_tool_from_candidates`
         now needs a story tagged `ai-tools` AND (`model-releases` or `agents`) AND none of
         `funding`/`ai-policy`/`ai-safety`/`ai-ethics`, else the card is omitted. Checked on real
         data: 2026-10-03 omits the card, 2026-10-02 picks the ChatGPT shopping launch. The tags
         are only a heuristic (the Writer tagged a smart-home camera story `ai-tools`); the proper
         design is a Writer-proposed `tool_name` that the Fact-checker verifies against the
         passages like entity tags - needs a prompt change, hence evals.
      3. **The AI section is mostly not about AI** (Sling TV, TechCrunch Disrupt discount
         passes): its only sources are general tech feeds. Needs AI-specific feeds or a
         relevance filter on the Writer's topic tags.
      4. **US football still leaks into Sport:** 'Chicago Bears ... has not named a starting
         quarterback' (Hindustan Times path /sports/football/, not /us-sports/) and, in longer
         reads, the older Bears injury story stored before the exclusion existed. A path
         exclusion is not enough; needs a title/URL term filter or an India-relevance rule.
      5. **The weekend block repeats the week's stories already shown above** (e.g. 'OpenAI
         Introduces Virtual Try-On' in both Technology and Longer reads) and the 'longer reads'
         are the normal short summaries, not the extended ones CLAUDE.md describes. The
         one-per-event dedup does not cover the weekend block.
      Still unchecked: Gmail MOBILE, Outlook, dark mode.

- [x] **Fixed: the four defects found in the first real email (2026-10-02).** Layout in Gmail
      desktop was otherwise good (masthead, dateline, boxes, extras, sources, image credit,
      footer links all correct). Fixes, each pinned by tests (877 pass):
      1. A followed genre with fewer than 2 stories now shows the "quiet news day" note
         (`quiet_genres()` in `render/selection.py`, `quiet_genres=` on `EmailRenderer.render`,
         HTML and plain text). An all-quiet reader still gets no newsletter, only the failure
         notice, exactly as before.
      2. One story per event: `drop_duplicate_events()` treats stories that cite the same
         source article URL as one event, across genres and within one, and keeps the
         best-ranked (ties: config genre order, then story id - deterministic). Checked on the
         real revision 3: Technology 4 -> 3, AI 5 -> 4, both repeats gone.
      3. US sports: new per-feed `exclude_paths` in `config/sources.yaml`; Hindustan Times'
         sports feed now skips `/sports/us-sports/` (recorded as drop reason `excluded_path`).
         Takes effect from the next collection, not for stored revisions.
      4. Weather shows one number when low == high.
      **New finding, not fixed:** the AI section is filled with general-tech stories (an AMD
      chip, an Apple camera, an Android blog) because its sources are general tech feeds
      (The Verge, TechCrunch). The AI genre needs AI-specific feeds or a relevance filter on
      the Writer's topic tags. Still unchecked: Gmail MOBILE, Outlook, dark mode, and the
      rendering of the new quiet-day note in real clients. Also: a 'Sign in to The Morning
      Mosaic' magic-link email arrived at 17:16 on 2026-10-02, not requested by the assistant.
- [x] **First real newsletter sent from production (2026-10-02 17:14 IST).** At the owner's
      request: real `mosaic-late-update` (ran clean, published nothing new - quota spent, as
      expected) then real `mosaic-delivery --slot 07:00`. The test subscriber's genres were
      widened from india+business to all five live genres so there was content (revision 3:
      ai 5, technology 4, sports 2, india/business quiet). Result: `deliveries` row
      `newsletter / sent / attempts 1 / no error / revision 3`; delivery run
      `{sent: 1, failed: 0, no_content: 0}`. Proves the whole path in prod: Cloud Run job ->
      selection -> render -> Gmail SMTP -> inbox. **Not yet checked by eye:** how the email
      renders in Gmail mobile and Outlook (still open under section 2), the PDF link, and the
      quiet-day sections. The test subscriber still follows all five genres; revert in
      preferences if wanted.

- [x] **Per-genre build diagnostics** (2026-10-02). Every build and late update now saves, per
      genre, into `pipeline_runs.detail["genres"]`: articles collected (total, by source,
      dropped by reason), clusters and whether the Ranker used the title-only FALLBACK
      clustering, whether it asked for more coverage, pooled stories and pool drops by reason
      (e.g. `insufficient_corroboration`), stories attempted/verified, total write-and-check
      cycles, and why stories were abandoned (`checker_unavailable`, `claims_unsupported`,
      `writer:<issue>`). Counts and reason keys only - no article text. `GenreDiagnostics` in
      `agents/schemas.py`, helpers in `agents/diagnostics.py`, wired in `graph/build_genre.py`;
      `python -m app.buildreport` prints it as "WHY EACH GENRE CAME OUT AS IT DID". 855 tests.
      **Not live until the images are rebuilt and redeployed**; the first night with it will
      confirm or kill the hypothesis that india/business lose to fallback clustering.
- [x] **Dry run with the new diagnostics (2026-10-02 ~16:00 IST, nothing published; script kept
      outside the repo): the hypothesis was half right.** 3.5 min, 1 of 5 genres publishable.
      * **business** - CONFIRMED: Ranker clustering fell back to titles (its model 429'd),
        79 clusters from 4 outlets, 78 dropped `insufficient_corroboration`, 1 pooled.
      * **india** - REJECTED: model clustering worked, 6 stories pooled; they died after that:
        `checker_unavailable` 2, `writer:copied_text` 1, Writer-model failures 3 (then filed as
        `writer:unparseable`, since fixed to `writer_unavailable`). 57 of 63 clusters were
        genuinely single-outlet, so corroboration is strict but not the blocker.
      * **technology** 3 verified; **ai** and **sports** 1 each (min is 2 -> quiet day), lost to
        Writer-model failures (Gemini quota 429 x85) and `checker_unavailable`.
      * Call volume is inflated ~3x by retrying outages: ai spent 17 write cycles on 6 stories.
      * LLM quota is therefore still THE blocker, and a dry run spends the same quota as a real
        build - this one was run ~12 h before the next scheduled build, inside the same Gemini
        quota window (resets 12:30 IST) and Groq's rolling day.
- [x] **Model outages no longer trigger rewrite retries (2026-10-02).** `is_outage()` in
      `llm/client.py` classifies a total LLM failure by its cause (HTTP 429/408/5xx or a dropped
      connection = outage; invalid JSON, empty completion, 400/413 = bad answer).
      `FactChecker` sets `CheckResult.unavailable` and the Writer files an outage as
      `WriterIssue.MODEL_UNAVAILABLE`; `write_and_verify` then abandons the story at once
      (1 call instead of up to 6) and still fails closed - nothing unchecked is ever published.
      Content failures (unsupported claims, bad Writer output) retry exactly as before; tests
      pin both sides. 863 tests pass; the deterministic evals (4) are unchanged.
      **Eval gate NOT fully met:** CLAUDE.md requires evals after a behaviour change, and the 4
      model-backed evals (groundedness, tag accuracy, catch rate full pipeline, clustering full
      pipeline) can only run with live quota. They were run once by accident on 2026-10-02
      under exhausted free-tier quotas: 6 passed, 2 failed - cause not captured (output lost)
      and probably quota. Rerun `uv run python -m evals.run --verbose` ONCE on a morning after
      reading the 04:15 build (it spends the same quota a build does), before relying on this.
- [x] **Morning build report:** `uv run python -m app.buildreport [--date YYYY-MM-DD]`
      (`backend/app/buildreport.py`, read-only): every build/late-update run for the date with
      duration and error, what was published per genre, LLM calls by agent and model with
      tokens, what the same tokens would cost on a paid plan, failed calls bucketed by cause
      (Cloudflare neurons, daily quota, per-minute rate limit, 413, invalid JSON), and the
      delivery rows. Use it first when reading any build.
      **Found with it:** `pipeline_runs` keeps 'running' rows for runs whose container was
      killed (timeout / my 600 s kill), e.g. 5 stale rows for 2026-10-01. A SIGKILL cannot
      update its own row; a janitor step at the start of each build should mark RUNNING rows
      older than their deadline as failed. Not built.

- [x] **Launch scope cut to 5 genres, pool 6** (owner decision 2026-10-01, free-LLM
      budget). New `enabled` flag on `Genre` (default true); `config/genres.yaml` turns off
      politics, gaming, bollywood, hollywood and music. Build and late update default to the
      enabled genres; `/api/config` lists only them; signup and `PATCH /api/me` reject a
      disabled genre ("not available yet"); the landing stamp sheet and copy come from
      `LIVE_GENRES` in `frontend/src/content/genres.ts`, and
      `backend/tests/test_launch_genres.py` fails if that list drifts from the YAML. Also
      fixed a test-isolation bug found on the way: tests read the developer's real `.env`
      (a newly added Turnstile secret made 7 signup tests fail), so `conftest.py` now
      disables `.env` loading for every test. 829 backend tests (with Postgres), 66 vitest
      and 207 Playwright tests pass. **Not yet done:** the deployed images still carry the
      old config - rebuild and redeploy both before this takes effect in prod; the
      existing test subscriber (india, business) is unaffected.

- [x] **Cloud Run job timeouts were 600 s for every job; the real build needs
      ~16 min.** The first manual build was killed at 600 s. Terraform now sets
      per-job timeouts (`local.job_timeout_overrides`): build 90 min, late-update
      25, delivery and failure-notice 30, the rest keep the 600 s default.
      Committed; **the apply is pending** (saved plan `infra/timeouts.tfplan`,
      4 timeouts change). Until applied, the 04:15 scheduled build would be
      killed at 10 minutes. A manual run can override with
      `gcloud run jobs execute mosaic-build --task-timeout=3600s --args=-m,app.jobs.build,...`
      (note `--args` replaces the whole argument list, so `-m,app.jobs.build`
      must be included).
- [x] **Dev test data was sitting in the production database** (12 editions
      dated 2026-10-01..15, 51 stories, 76 articles, built Sept 18-28) because
      dev and prod share one Neon database. It would have crashed every
      scheduled build ("already has a published revision") and could have let
      delivery send September stories as current news. Deleted 2026-10-01 by
      the owner in one guarded transaction after a local backup; subscriber,
      consent, token, city and source rows were untouched. **Follow-up:** dev
      and prod must not share a database again - add a separate Neon branch for
      dev before running any more local builds.

- [x] **First deploy to GCP (project `the-morning-mosaic`, `asia-south1`), 2026-10-01.**
      State bucket `the-morning-mosaic-tfstate`; 2 Cloud Run services, 7 jobs,
      14 Scheduler triggers, 4 alert policies, 18 secrets populated. Live at
      `https://mosaic-web-297073209731.asia-south1.run.app` (`BASE_URL`): all pages 200,
      `/api/config` returns 10 genres and 87 cities from the real database,
      no error-level logs. Images are the manual `:manual` tag; the Turnstile
      site key is confirmed inside the web image's bundle. Things that bit:
      a first `terraform apply` ran concurrently with a second and left the
      state behind reality (4 secrets + the registry repo existed but were
      untracked; fixed with temporary `import` blocks, nothing destroyed);
      two alert policies failed once because their log metrics were not
      registered yet (retry worked); `newsapi-key` was dropped from Terraform
      (unused, empty values are rejected). The prod `TOKEN_SIGNING_KEY` is a
      fresh key, not the dev one. **Not yet done:** a real signup/opt-in
      round trip in prod, a manual build + delivery run, preflight `--prod`
      against prod values, HSTS header (none sent), Workload Identity
      Federation for `deploy.yml`, and the `BASE_URL` CI-reset bug above.
      **Signup verified in prod 2026-10-01** (Turnstile passed after both run.app
      hostnames were added to the widget; error 110200 before that): POST
      /api/signup 200, opt-in GET+POST 200, user `pending` -> `active`, 1 consent
      row, opt-in token marked used. **Found:** uvicorn's access log writes full
      request paths to Cloud Logging, so opt-in, unsubscribe and feedback tokens
      (unsubscribe tokens never expire) sit in request logs readable by anyone
      with log access; scrub or suppress token paths in the access log.
      `terraform plan` always shows 2 in-place changes (Cloud Run `scaling`
      fields going 0 -> unset): provider noise, harmless.

- [x] **Critical: the Turnstile site key never reached the production
      frontend.** `TurnstileWidget` reads `NEXT_PUBLIC_TURNSTILE_SITE_KEY`, which
      Next inlines into the client bundle at *build* time; the Dockerfile and
      `deploy.yml` passed nothing, so the prod widget would render nothing and
      every signup would be rejected (missing token). `frontend/Dockerfile` now
      takes it as a build arg; `deploy.yml` passes `vars.TURNSTILE_SITE_KEY`
      (and `LLM_SECONDARY_URL`, `TURNSTILE_SITE_KEY` to terraform); the manual
      build in `infra/README.md` shows the flag. Verified with a plain
      `npm run build` and a marker key found in `.next/static` - the Docker
      image itself was not built (Docker Desktop was not running). New
      repository variables to set: `TURNSTILE_SITE_KEY`, `LLM_SECONDARY_URL`.

- [x] Pre-flight check: `uv run python -m app.preflight [--live] [--prod]`
      (`backend/app/preflight.py`, 15 tests in `test_preflight.py`). Offline:
      settings validate, config YAML validates, prod-only rules (https
      `BASE_URL`, public LLM URL, signing-key strength, Turnstile, GCP/bucket,
      direct DB URL with a pooled one, Gmail subscriber cap), `launch_date`,
      and drift between `Settings`, `.env.example` and Terraform. `--live`
      adds read-only DB (reachable, migrated to head, seeded), SMTP and IMAP
      logins, LLM gateway auth and a Turnstile secret probe. Never prints
      secret values; nothing sent. First run against dev: 0 failures. Not
      covered: a real Turnstile widget token, and the optional providers'
      keys are checked for presence only.

- [x] Website redesign steps 1–2: token pipeline (`frontend/design/tokens.json`
      → `src/styles/tokens.css`, contrast check over 102 pairs), self-hosted
      fonts, Morning/Late themes with pre-paint script, paper grain, halftone
      and misregistration utilities, restyled `ui.tsx` primitives, Dateline,
      Masthead, ThemeToggle, postage-stamp GenreCard — this commit

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
- [x] **`LlmClient` itself now retries a malformed (unparseable) response
      when `json_object=True`**, instead of every JSON-consuming agent
      discovering the problem separately after the fact. Chosen over the
      first draft of this fix (a retry loop added only inside
      `FactChecker._model_claims`): a direct diagnostic showed the *Writer*
      hits the identical failure shape (a 200 OK with content that doesn't
      parse), on a completely different pinned model
      (`gemini-flash-lite-latest` vs the Fact-checker's Cloudflare
      `llama-3.3-70b`) — so this isn't one model's quirk, it's a property of
      `json_object` mode on budget-tier models generally, and belongs in the
      one place every such call already goes through.
      `_call()` now parses `content` when `json_object` was requested and
      raises `LlmProtocolError` on failure — already a member of
      `_is_retryable`'s set, so the existing per-route retry/backoff loop
      (`_try_routes`) handles it with no new retry logic needed at the
      client layer either.
      Also fixed, found while doing this: **four separate, near-identical
      `_strip_fence`/`strip_json_fence` helpers** (Writer, Fact-checker,
      Ranker, Image finder) had silently drifted — three stripped only up to
      the first newline after a ` ```json ` fence, missing a single-line
      `` ```json{...}``` `` fence entirely (leaving the literal word "json"
      prepended to what got handed to `json.loads`); Image finder's own copy
      had already patched exactly that case independently. Unified into one
      `strip_json_fence()` in `app/llm/client.py`, built to handle every
      shape all four originals covered between them, and every agent now
      imports it instead of keeping its own copy.
      Reverted the first draft's `FactChecker`-level retry loop once the fix
      moved to the right layer — the two tests it added there were replaced
      with one confirming `FactChecker` still fails closed once `LlmClient`
      itself genuinely exhausts its attempts, and the real retry-and-recover
      behaviour is tested once, correctly, in `test_llm_client.py` (7 new
      tests there: recovery, exhaustion, that non-JSON calls are never
      checked against this rule at all, and four `strip_json_fence` shape
      cases including the one three of the four originals missed).
      Verified live, not just unit-tested: post-fix, 15 live `evals.run`
      groundedness runs passed 10 times (67%) versus 1 of 8 (12.5%) before —
      see the still-open entry above for the two runs that didn't and why
      that comparison isn't the end of the story. Full suite now **773
      tests**, `mypy --strict` and `ruff` clean.
- [x] **All 21 lunar festival dates filled in** for the whole window the
      calendar already covers (2026-10 through 2027-12), from the actual
      authoritative source the file's own header names — not guessed, not
      taken from a secondary summary. Found the Government of India's real
      DoPT holiday notifications for both years via web search, then
      fetched the official PDFs directly from `dopt.gov.in` — both turned
      out to be scanned images (`WebFetch` couldn't extract text from
      either), so read them with vision instead of giving up or falling
      back to a secondary source. Cross-checked the 2027 gazetted subset
      against two independent secondary sources (staffnews.in,
      postalstudies.com) before trusting it, matching this project's own
      corroboration standard; the primary document itself is authoritative
      for the rest.
      `config/editions.yaml`: `awaiting_dates` is now empty, and 26 new
      `special_editions` entries (5 for the Oct–Dec 2026 window right after
      launch: Dussehra, Diwali, Bhai Dooj, Chhath Puja, Guru Nanak Jayanti;
      21 for all of 2027) join the 9 already there. Verified no duplicate
      keys and no two entries sharing a date (`EditionsConfig`'s own
      validators, which would have caught either) — checked by hand first
      against the real source data, since a clash was plausible (the 2027
      memo itself flags Independence Day and Milad-un-Nabi coinciding that
      year; neither is one of our 21, so no actual collision). Left
      `accent` unset on every new entry — that's a design choice with no
      ground truth to verify, unlike the dates, and the template already
      falls back to a sensible default color when it's absent.
      Deliberately did not extend past 2027-12 — the note left in the file
      says to redo this the same way (the DoPT notification is typically
      published 5-6 months ahead) rather than guess forward. No code
      change; `load_editions()` already validates whatever's in the file.
      Full suite re-run after the config change: still 773 tests passing.
- [x] **The seed job now needs only `DATABASE_URL`, not the ten other
      variables the full app `Settings` requires.** Resolved "undecided
      whether to loosen" by not touching `Settings` at all — weakening it
      (making fields optional) would drop the guarantee every other
      consumer relies on, that a constructed `Settings` means a fully
      configured app. Instead: a new, narrower `SeedSettings` (just
      `database_url`) and `get_seed_engine()`/`seed_session_scope()`/
      `dispose_seed_engine()` in `app/db/engine.py`, same pooling/
      `prepare_threshold` reasoning as the shared engine, built from
      `SeedSettings` instead. `app/jobs/seed.py` is the only caller.
      Verified the friction is actually gone, not just plausible: a real
      subprocess test (`test_the_job_runs_with_only_database_url_set`)
      runs `python -m app.jobs.seed --dry-run` with a genuinely stripped
      environment (`DATABASE_URL` and nothing else the app would
      otherwise need) against the real test database. `--help` alone
      would not have proven this — argparse exits during `parse_args()`,
      before `main()` ever constructs a settings object, which is
      probably why this friction went unnoticed as long as it did.
      Found and fixed a real, separate latent issue while writing this:
      the comment on `test_config.py`'s `_settings()` helper claimed
      "`model_validate` bypasses the env/.env sources, so a developer's
      local `.env` cannot change the outcome of these tests" —
      empirically false (`Settings.model_validate({})` and
      `SeedSettings.model_validate({})` both silently succeed using the
      real `.env`'s values instead of raising). No current test actually
      relied on the false guarantee (every one of the dozen files using
      this pattern always supplies every field explicitly), so nothing
      was silently wrong — corrected the comment so a future test doesn't
      omit a field expecting rejection and get an environment-dependent
      result instead. Checked `SeedSettings` requires `database_url` via
      `model_fields[...].is_required()` instead, which needs no env
      isolation claim to be true.
      3 new tests; full suite now **776 tests**, `mypy --strict` and
      `ruff` clean.
- [x] **Bounce parsing verified end to end against a real Gmail DSN, not
      just synthetic fixtures.** Confirmed real IMAP connectivity first
      (`ImapBounceSource.fetch()` against the real, already-provisioned
      `imap.gmail.com` account — connects, logs in, searches, zero
      mailer-daemon messages found in the last 30 days, as expected since
      nothing had ever bounced). Then triggered a real one: sent a real
      email over real Gmail SMTP to a guaranteed-nonexistent address at
      the sender's own domain (`definitely-nonexistent-<random>@gmail.com`
      — Gmail-to-Gmail, so the real bounce came back in **3 seconds**, not
      the async delay the module's own docstring describes for other
      domains). `ImapBounceSource` found it, and `parse_bounce()` correctly
      extracted the real recipient, `permanent=True`, `status="5.1.1"` from
      the actual RFC 3464 report — not a hand-written fixture.
      Then ran the full job, not just the parser: inserted a real `User`
      row in the test database with that exact bounced address, called
      `run_bounces()` with the real `ImapBounceSource` as its source, and
      confirmed the report (`examined=1 permanent=1 marked=1`) and that the
      user's `status` actually flipped to `bounced` — the complete real
      path, mailbox to database row, not a mock anywhere in it.
      No code change — the parser and job were already correct; this
      replaces "never verified against anything real" with an actual
      verified result. One side effect worth knowing: the real bounce
      notification itself is still sitting in the sender's real inbox —
      `ImapBounceSource` opens it read-only by design (see the module's own
      docstring on why), so nothing here can delete it.
- [x] **The PDF page-break gap found while verifying WeasyPrint against a
      real section is fixed.** `_story.html.j2`'s `<article>` — shared by
      the email, the web archive, and every PDF page, so one change covers
      all three — now carries `page-break-inside:avoid;break-inside:avoid;`
      inline. Harmless where it doesn't apply (email clients and browsers
      simply ignore it; it only does anything at all in a paginated
      context like WeasyPrint's).
      Verified the fix for real, not just by inspecting the template: the
      already-published `EditionSection.html` row in the database predates
      the fix, so re-used it would have silently proven nothing. Instead
      rebuilt the Docker image, re-rendered the same real gaming/2026-10-15
      stories fresh through `SectionRenderer.render_candidates()` (the
      now-fixed template), confirmed `page-break-inside:avoid` actually
      landed in the freshly-generated HTML, then rendered that through the
      real `weasyprint_renderer()` and read the resulting PDF: every story
      now stays intact on one page — the exact story that split across
      the page 1/2 boundary before (body on page 1, "Source:" stranded at
      the top of page 2) now has both on the same page, and the next story
      starts cleanly on the next one instead. One new test
      (`test_a_story_does_not_split_across_a_pdf_page_break`); full suite
      now **777 tests**, `mypy --strict` and `ruff` clean.
- [x] **A real, critical Terraform bug found and fixed while auditing
      `docs/architecture.md` against the code for staleness (the same kind
      of audit that caught the bounce/late-update/agent-count staleness
      elsewhere in this file).** `architecture.md` had no Observability
      section at all — missing both the structured-logging and the
      Langfuse work from earlier today — so added one. Writing it surfaced
      that `infra/locals.tf`'s `common_env` set `LANGFUSE_PUBLIC_KEY`/
      `LANGFUSE_SECRET_KEY` as real secrets but never `LANGFUSE_HOST` at
      all, which `build_langfuse_client()` also requires before it does
      anything.
      Added the missing `langfuse_host` Terraform variable (empty default,
      same pattern as `llm_fallback_url`/`turnstile_site_key`) and wired it
      into `common_env` — then found a second, worse bug while doing it:
      an empty-string Terraform default was being set as a literal `""`
      Cloud Run env var rather than left unset, and confirmed directly
      (constructed `Settings` with `LANGFUSE_HOST=""` and watched it fail)
      that pydantic accepts a genuinely absent env var as `None` for an
      `AnyHttpUrl | None` field but rejects `""` outright. Every workload
      would have crashed at startup the day this was ever actually
      deployed with Langfuse (or the pre-existing `LLM_FALLBACK_URL`)
      left unconfigured — never caught before because nothing has been
      deployed yet (no GCP project). Fixed generally, not just for these
      two: `common_env` now filters out any variable still at its
      empty-string default before it reaches the container, so a field
      left unconfigured is genuinely absent rather than present-and-empty.
      `terraform fmt` and `validate` both pass (no GCP project to `plan`/
      `apply` against, same limitation this file already records
      elsewhere); no Python code changed.
- [x] **Restored the "draft, pending legal review" disclosure on `/privacy`
      and `/terms`, wrongly removed entirely by the earlier
      real-policy-config change.** That change correctly replaced every
      bracketed placeholder with real values, but its Done entry above also
      records removing "the 'pending legal review' banner" — the visible
      warning that the wording itself hasn't had legal review, a fact that
      is still true today and stays true independent of the facts on the
      page being real. Found auditing `frontend/README.md`, which still
      (correctly) said "see the in-page notice" for those two pages — there
      no longer was one, a real, user-facing regression, not a docs nit.
      Restored a `<Notice>` on both pages with corrected wording (no longer
      naming specific placeholders, since those are genuinely gone) that
      says plainly: the operator/date/contact facts are real, the phrasing
      is not final. 2 new tests confirming the disclosure renders; verified
      live against the actual running dev server (still up from earlier
      today) that both pages show it. Full suite: 38 frontend tests,
      `eslint`, `tsc`, and `next build` all clean.
- [x] **A reader's session cookie can now be revoked before it expires** —
      the first of four accepted trade-offs the owner asked to actually fix
      rather than leave accepted. Deliberately scoped to the reader session
      only, not the admin one: the admin session's 12-hour TTL (versus a
      reader's 30 days) was already reasoned as the accepted mitigation for
      the same gap, and CLAUDE.md never asks for revocation there.
      New `user_sessions` table (migration `ec5914620e4f`, upgrade/downgrade
      verified against a real Postgres): one row per login, its id embedded
      in the session token as a new `sid` claim. `issue_session()` creates
      the row; `current_user_id()` checks `revoked_at IS NULL` on every
      request in addition to verifying the signature — a real, accepted
      extra cost (one indexed lookup per authenticated request, negligible
      at this project's traffic per ADR 0001) for a real fix, not free.
      `clear_session()` (logout) now revokes the row instead of only asking
      the browser to forget the cookie; `POST /api/me/delete` revokes every
      session the account ever had, not just the current one — the same
      precedent the route already followed for `Token` rows. A session
      token issued before this migration (no `sid` claim) is treated as
      unusable rather than trusted on signature alone — a one-time forced
      re-login for anyone signed in at deploy time, accepted the same way a
      `TOKEN_SIGNING_KEY` rotation already forces one.
      Verified the fix is real, not just plausible: a test captures the raw
      cookie value before logout, logs out, then replays that exact value
      in a fresh client — confirmed this test genuinely fails against the
      pre-fix code (200, not 401) by temporarily reverting the fix and
      rerunning it, the same "prove the regression test catches the
      regression" rigor used elsewhere this session. Also added expired-
      session cleanup to the purge job (`user_sessions_cleared`), matching
      the existing `rate_limit_hits` precedent so the table doesn't grow
      forever. `docs/architecture.md` updated. 6 new tests; full suite now
      **781 tests**, `mypy --strict` and `ruff` clean.
- [x] **CSRF verification now checks a per-session server-side secret, not
      just that the cookie matches the header.** The second of four accepted
      trade-offs the owner asked to actually fix. The `user_sessions` table
      from the session-revocation fix already gave this a natural home: a
      new `csrf_secret` column (migration `cd675f150551`), generated once at
      login and stored on the row. The double-submit *shape* is unchanged —
      a non-HttpOnly cookie still carries the value so script can echo it as
      a header, since that's still the only way script learns it — but
      `require_csrf` now resolves the session through the trusted, HttpOnly
      session cookie and compares the header against `csrf_secret` on that
      row, never against the client-supplied CSRF cookie itself. The exact
      gap this closes: previously, an attacker who could set a cookie on
      this origin at all (a subdomain takeover) could pick any value, echo
      it as the header themselves, and pass, because both sides were
      client-supplied and only checked against each other.
      Verified with the same rigor as the session-revocation fix: a test
      sets an attacker-chosen value as both the CSRF cookie and header
      (simulating exactly that attack) and expects 403; confirmed it
      genuinely returns 200 against the pre-fix code by reverting both the
      code and the migration and rerunning it. `docs/architecture.md`'s
      session doc comment already generalised to cover this. 1 new test
      (plus 2 existing purge-job fixtures updated for the new required
      column). A background full-suite run was killed by the host's own
      memory pressure mid-run, not a test failure; re-ran it clean once
      that passed — full suite now **782 tests**, `mypy --strict` and
      `ruff` clean.
- [x] **`PATCH /api/me` now supports an optional `Idempotency-Key` header.**
      The third of four accepted trade-offs the owner asked to actually fix.
      New `idempotency_keys` table (migration `ef0f927aed1a`): a client that
      sends the header and retries the exact same request gets the first
      response replayed instead of the update reapplied; a client that
      never sends it keeps today's behaviour exactly. A concurrent race
      between two identical retries is handled with a `SAVEPOINT`
      (`session.begin_nested()`) around just the key's own insert, not the
      whole request — the same shape as `weather.py`'s existing
      `WeatherCache` race handling, but scoped narrower on purpose: unlike
      that case, rolling back the *outer* transaction here would have
      discarded the real preference update alongside the harmless
      bookkeeping conflict.
      Verified with the same rigor as the other two fixes: a test retries a
      PATCH with the same key after a *different*, real edit happened in
      between, and confirms the retry returns the first response while the
      intervening edit survives untouched — confirmed this genuinely fails
      against the pre-fix code (the retry clobbers the intervening edit)
      by reverting and rerunning it.
      Deliberately did not touch the frontend: `readerPatch` has no retry
      logic today, so sending the header from a client that only ever
      makes one attempt per save would be unused plumbing protecting
      nothing — this closes the gap the backlog item actually named (no
      *server-side* mechanism to protect a retry, at all), not a new
      client-retry feature nobody asked for. Also added stale-key cleanup
      to the purge job (`idempotency_keys_cleared`, 1-day retention — a
      dropped-response retry happens in seconds, never days), matching the
      `rate_limit_hits`/`user_sessions` precedent. 5 new tests; full suite
      now **787 tests**, `mypy --strict` and `ruff` clean.
- [x] **A real website-downtime status page exists.** The fourth and last of
      the four accepted trade-offs the owner asked to actually fix. CLAUDE.md:
      "Website downtime is shown as a status message on the site, not
      emailed, unless it stops the newsletter." Scoped exactly to what's
      actually buildable without a GCP project: manual, not automated — an
      admin flips it during a real incident, the same way many real status
      pages work — rather than invent a self-monitoring pipeline the
      "Monitoring covers two conditions, not the four CLAUDE.md lists" item
      already tracks separately as its own, GCP-dependent gap.
      New `site_status` table (migration `d1dc560f47a7`, a singleton row —
      `id=1`, upserted, never appended to, since only the *current* status
      is ever read), `GET /api/status` (no auth — this must work precisely
      when something else might be broken), and `POST /admin/api/status`
      (auth + CSRF, matching every other admin write). A new `/status` page
      (linked from the site footer alongside Privacy/Terms/Admin) shows
      "All systems operational" or the real recorded message; a new "Site
      status" section on the admin dashboard sets or clears it, with the
      current state shown before the form.
      Verified live, end to end, not just in tests: restarted the backend
      against the real Neon database (ran all four of today's new
      migrations against it for the first time, not just the local test
      Postgres), set a real degraded status directly, confirmed
      `GET /api/status` reflected it, confirmed the real running frontend's
      `/status` page rendered the real message, then restored the
      operational default. 13 new tests (7 backend, 6 frontend); full
      backend suite now **794 tests**, full frontend suite **44 tests**,
      `mypy --strict`, `ruff`, `eslint`, `tsc`, and `next build` all clean.
      This closes all four of the trade-offs from this batch — session
      revocation, server-side CSRF, PATCH idempotency, and this — the only
      remaining open items are external-account blockers (GCP, Turnstile,
      a git remote) or things that were never trade-offs to begin with.
- [x] **The two missing monitoring signals now exist: all four of CLAUDE.md's
      alert conditions have a real Cloud Monitoring alert policy.** A
      build's deadline miss and a sharp drop in verified story counts had
      no Cloud Run metric to attach to — both are properties of a job's own
      outcome, recorded only in `pipeline_runs` (Postgres/Neon, outside
      GCP's own metrics). Structured JSON logging already existed
      (`app/logging_config.py`) but nothing used it for this; a
      `google_logging_metric` per condition is the bridge, each counting a
      specific literal in the job's own log stream, wired to an alert
      policy exactly like the two Cloud-Run-native ones already had.
      `app/jobs/build.py`: `_check_story_count_drop` compares today's
      `stories_persisted` against the mean of the last 7 earlier builds
      that actually ran (`SUCCEEDED` or `DEADLINE_MISSED`), and logs
      `verified_story_count_drop` when today is under half that baseline —
      deliberately conservative (a real alert pages someone) and
      deliberately inert with fewer than 3 days of history, so launch week
      and a slow news day don't fire it on their own; there is no
      absolute "too few stories" number that would mean the same thing on
      both days. Confirmed with fixture `pipeline_runs` rows standing in
      for a real week's history, not just unit-level logic. Both
      `app/jobs/build.py` and `app/jobs/late_update.py` log the exact same
      `build_deadline_missed` message on a missed publish deadline — a
      shared, greppable literal was the deliberate choice over matching on
      log level alone, since WARNING covers other things each job logs too.
      `infra/monitoring.tf` gained two `google_logging_metric` resources and
      two `google_monitoring_alert_policy` resources; `terraform fmt` and
      `validate` both pass. Verified the actual log shape live, not just
      assumed: ran `configure_logging` for real and confirmed both messages
      render as `{"event": "build_deadline_missed ...", "level": "warning",
      ...}` — the exact `jsonPayload.event` shape the Terraform filter
      matches on. Like the two pre-existing alert policies, none of the
      four has ever fired for real — `terraform apply` still hasn't run
      against a real project (Blockers) — but that gap is now identical
      across all four instead of only two. 6 new backend tests (2 for the
      deadline-miss log line across both jobs, 4 for the drop check: fires
      against a real baseline, stays silent with too little history, stays
      silent when today's count doesn't actually drop sharply); full suite
      now **800 backend tests**, `mypy --strict` and `ruff` clean.
