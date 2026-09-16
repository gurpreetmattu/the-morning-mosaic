# Backlog

Running list of what is pending, what is provisional, and what is known to be
broken. Kept in the repo so it survives between sessions.

**Convention:** update this file at the end of every step, in the same commit
as the work. Move finished items to "Done" with the commit that closed them.
Add anything discovered mid-task rather than leaving it in a chat message.

- **Last updated:** 2026-09-17, at commit `0436f55`
- **State:** 8 commits · 28 modules · 82 tests (all green, database included) ·
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

## 2. Defects and gaps in code that already exists

- [ ] **No structured logging.** `structlog` is a dependency but unused; the
      seed job prints. CLAUDE.md requires JSON logs to Cloud Logging. Worth
      doing before more agents land, since each will want it.
- [ ] **No Langfuse tracing** wired, though it is a dependency and in the spec.
- [ ] **No crawl throttling or `Crawl-delay` support.** `RobotsPolicy` honours
      allow/disallow and caches per run, but nothing rate-limits requests to a
      single host. With feeds enabled this could hammer a publisher.
- [ ] **`Fetcher` retry/backoff is not directly tested.** Exercised indirectly
      by the collector tests, never asserted.
- [ ] **Neon-specific engine settings untested against Neon.** `pool_pre_ping`
      and `prepare_threshold=None` were reasoned from PgBouncer behaviour and
      have only run against local PostgreSQL.
- [ ] **Seed job requires every env var** just to read `DATABASE_URL`. Fine in
      Cloud Run, friction in dev. Undecided whether to loosen.
- [ ] **Job entry points need `PYTHONPATH=backend` set by hand.** The project
      is not installed (`[tool.uv] package = false`), so `python -m app.jobs.*`
      fails from a clean shell; only pytest works, via its own `pythonpath`.
      Will hit every job and the Cloud Run image. Likely fix: make the project
      a real package with `packages = ["backend/app"]`.
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

**Agents** (1 of 10 done — Collector)
- [ ] Orchestrator (1) · [ ] Ranker (3) · [ ] Writer (4) · [ ] Fact-checker (5)
- [ ] Image finder (6) · [ ] Weather (7) · [ ] Layout (8) · [ ] Delivery (9)
- [ ] Feedback (10)

**Pipeline**
- [ ] LangGraph build graph · [ ] late-update graph
- [ ] Jobs: build, late_update, delivery, failure_notice, bounces (only `seed`
      exists)
- [ ] Versioned prompts — none exist, so `prompt_version` has no source yet

**Delivery path**
- [ ] Email sender, tokens, `List-Unsubscribe` one-click, link-scanner-safe GETs
- [ ] Jinja templates: per genre, special, weekend, system notices
- [ ] PDF assembly and Cloud Storage caching

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
