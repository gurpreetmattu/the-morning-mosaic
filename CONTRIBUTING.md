# Contributing

Read [`CLAUDE.md`](CLAUDE.md) first: it holds the product decisions and the grounding rules.
Anything under "Product decisions" needs the owner's sign-off before it changes.

## Ground rules

- Never weaken grounding, freshness, balance or source rules to make a test pass or a story appear.
- No secrets in the repo. Test fixtures and eval datasets must not contain full copyrighted
  articles: use short excerpts or synthetic text.
- Unit tests use saved fixtures; no live API or LLM calls.
- Never send personal data (names, emails, cities, user IDs) to any LLM.
- Do not add a dependency without saying why in the PR.
- A prompt or model change requires rerunning evals (`uv run python -m evals.run`).

## Workflow

1. Branch from `main`: `feat/…`, `fix/…`, `docs/…`, `chore/…`.
2. Keep changes small and tested. Add tests alongside the code.
3. Run the checks listed in the [README](README.md#checks).
4. Update `docs/BACKLOG.md` in the same PR (move finished items to "Done"; record anything
   deferred). Record significant decisions as an ADR in `docs/adr/`.
5. Open a PR using the template. CI must be green before merge.

## Commit messages

Imperative, sentence case, one logical change, explaining the why when it is not obvious
(e.g. `Stop the late update crashing when its LLM phase runs long`).

## Migrations

Alembic migrations must be reversible where practical and are tested in
`backend/tests/test_migrations.py`. Never edit a migration that has been applied in prod; add a new
one.
