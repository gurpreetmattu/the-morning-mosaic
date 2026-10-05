# The Morning Mosaic

[![CI](https://github.com/gurpreetmattu/the-morning-mosaic/actions/workflows/ci.yml/badge.svg)](https://github.com/gurpreetmattu/the-morning-mosaic/actions/workflows/ci.yml)
[![Nightly evals](https://github.com/gurpreetmattu/the-morning-mosaic/actions/workflows/evals-nightly.yml/badge.svg)](https://github.com/gurpreetmattu/the-morning-mosaic/actions/workflows/evals-nightly.yml)

A multi-agent AI newsletter for India. Readers pick genres, subscribe, and get one
personalised, newspaper-styled email each morning at their chosen time, with an optional A4 PDF.

**Principle: every factual statement comes from a fetched, credible source and is traceable to
it.** The LLM rephrases sources; it never supplies facts. When in doubt, the item is dropped. A
missing item is acceptable; a wrong one is not.

## How it works

Scheduled Cloud Run jobs collect news from whitelisted sources, rank and cluster it, write each
story with per-sentence citations, and fact-check every claim (partly in code) before anything is
published. Personalisation is done in code from verified story pools, with no per-user LLM calls.
The audit trail keeps every published sentence with its sources.

See [`docs/architecture.md`](docs/architecture.md) for the system diagram, and
[`CLAUDE.md`](CLAUDE.md) for the full product and engineering spec.

## Repository layout

| Path | Contents |
|------|----------|
| `backend/app` | FastAPI API, agents, LangGraph graphs, jobs, LLM client, rendering |
| `backend/migrations` | Alembic migrations |
| `backend/tests` | Unit tests (saved fixtures, no live network or LLM calls) |
| `frontend` | Next.js (App Router) + Tailwind site |
| `evals` | Groundedness, freshness, clustering, fact-checker, tag and neutrality evals |
| `config` | Sources, genres, models, editions, cities (YAML) |
| `infra` | Terraform for GCP (`asia-south1`) |
| `docs` | Architecture, ADRs, runbooks, [`BACKLOG.md`](docs/BACKLOG.md) |
| `DESIGN.md` | Website design system |

## Getting started

Requirements: Python 3.12, [`uv`](https://docs.astral.sh/uv/), Node 22, PostgreSQL (Neon or local).

```sh
cp .env.example .env          # fill in values; never commit .env
uv sync
uv run alembic -c backend/alembic.ini upgrade head
uv run python -m app.jobs.seed
uv run uvicorn app.api.app:create_app --factory --reload

cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Outside `APP_ENV=prod`, email is restricted to `TEST_EMAIL_ALLOWLIST`, so development never
mails real subscribers.

## Checks

```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy backend evals
uv run pytest
uv run python -m evals.run

cd frontend && npm run lint && npm run typecheck && npm test
cd infra && terraform fmt -check -recursive
```

CI runs all of these on every pull request.

## Project status

Pending, provisional and known-broken work is tracked in [`docs/BACKLOG.md`](docs/BACKLOG.md).

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Report vulnerabilities privately as described in
[`SECURITY.md`](SECURITY.md); do not open a public issue.
