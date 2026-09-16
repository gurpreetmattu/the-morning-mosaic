# Backlog

Running list of what is pending, what is provisional, and what is known to be
broken. Kept in the repo so it survives between sessions.

**Convention:** update this file at the end of every step, in the same commit
as the work. Move finished items to "Done" with the commit that closed them.
Add anything discovered mid-task rather than leaving it in a chat message.

- **Last updated:** 2026-09-17, at commit `f032aa0`
- **State:** 36 commits · 56 modules · 340 tests (all green, database included) ·
  ruff and `mypy --strict` clean

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
- [ ] **Rows stuck in `sending` are counted but not surfaced.** Delivery
      deliberately never retries them, and CLAUDE.md says they should be
      "flagged for review". Nothing flags them yet; the admin dashboard does
      not exist.
- [ ] **No admin alerting.** CLAUDE.md wants Cloud Monitoring notifications on
      build failure, deadline miss, send failures and sharp drops in verified
      story counts. The build job records everything needed in `pipeline_runs`
      but tells nobody.
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
- [ ] **`premailer` is an unused dependency.** Sections are written with inline
      styles directly, so nothing inlines a stylesheet. Either the full email
      template will need it, or it should be dropped.
- [ ] **Section HTML has never been seen in a real mail client.** It is built
      to the email-safe rules (inline styles, no classes, no flexbox) and tests
      assert those, but CLAUDE.md requires checking Gmail web and mobile plus
      Outlook. Nothing has been sent anywhere.
- [ ] **`LLMBUFFET_*` naming lags upstream.** The package was renamed to
      `freellmpool`; settings, `.env.example` and CLAUDE.md still say
      LLMBuffet. Cosmetic, but it spreads with every new reference.

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
- [~] Layout (8) — sections, per-user selection and full email assembly are
      done. Still to do: PDF pages via WeasyPrint, and the extras the masthead
      leaves room for (weather box is wired but has no Weather agent feeding
      it; market strip, quiz, quote and "On this day" are not built).

**Pipeline**
- [ ] LangGraph build graph · [ ] late-update graph. The Orchestrator runs the
      per-genre pipeline as plain code today; CLAUDE.md specifies LangGraph.
      Decide whether to wrap it or amend the spec.
- [ ] Jobs still to write: bounces, feedback aggregation (`seed`, `build`,
      `delivery`, `failure_notice` and `late_update` exist)
- [ ] **A late update never withdraws a story, only adds.** CLAUDE.md's admin
      kill switch needs the opposite: publishing a revision *without* a story.
      `story_withdrawals` exists as a table and nothing writes to it.
- [ ] **"New story" is judged by source URL.** A publisher that reissues the
      same story under a fresh URL will be appended twice by the late update.
      Content-hash comparison across clusters would be the stronger check.
- [ ] **A held notice batch cannot be approved or suppressed yet.** The job
      honours both states, but only the admin dashboard can set them, and it
      does not exist. Until then an abnormal batch simply expires at noon.
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
- [ ] Link-scanner-safe GET endpoints (opt-in, magic link, unsubscribe,
      feedback must not change state on GET)
- [ ] Jinja templates: full email shell with masthead, special, weekend,
      system notices
- [ ] PDF assembly and Cloud Storage caching
- [ ] Bounce handling over IMAP

**Services**
- [ ] weather · [ ] markets · [ ] sports · [ ] releases · [ ] deals
- [ ] images · [ ] quotes / "On this day"

**Surfaces**
- [ ] FastAPI routes (signup, opt-in, preferences, magic link, unsubscribe,
      feedback, archive, PDF, admin)
- [ ] Next.js frontend, including privacy policy and terms pages

**Supporting**
- [ ] Terraform in `/infra` · [ ] Evals in `/evals`
- [ ] GitHub Actions (lint, type-check, tests, eval subset on PRs)
- [ ] `docs/`: architecture doc, DPDP incident runbook, operational runbooks

## 5. Environment

- [ ] **WeasyPrint cannot run on this machine** (no GTK/Pango). PDF output is
      testable only inside a container.
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
- [x] Build job: the full pipeline behind one command, single-instance job
      lock, pipeline_runs tracking — `43adec4`. Run end to end against the
      live database: it correctly refused to publish, because no source has
      confirmed terms yet, and recorded the failure with diagnostics.
