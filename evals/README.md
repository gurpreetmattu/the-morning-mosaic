# Evals

CLAUDE.md: "Groundedness (share of claims supported), freshness (story age
at send), dedup/clustering accuracy, fact-checker catch rate on planted
errors, tag accuracy, political neutrality checks. Any prompt or model
change requires rerunning evals; regressions block merge."

```
uv run python -m evals.run [--verbose]
```

Exits non-zero if anything failed. `--verbose` prints every case, not just
the failing ones.

## Two tiers, not one report

Several of CLAUDE.md's evals depend on code that itself calls the LLM
gateway (Groq — a real, publicly reachable endpoint; see
`docs/BACKLOG.md`'s now-closed gateway-reachability blocker for why that
matters). It can still be down, rate-limited, or between free-tier quota
and a real key, so rather than let the whole suite fail whenever it's
unreachable, each eval that needs it is split, or skipped outright, so a
run always says something true:

| Eval | Needs the LLM? | What runs without it |
|---|---|---|
| `freshness` | No | Full eval — a pure function of fixture timestamps. |
| `fact_checker_catch_rate` | Partly | The deterministic tier (`unsupported_facts`) catches four of the seven planted-error categories — wrong figure, wrong day, wrong person, an invented fact with a number — on its own. The full pipeline (adding reversed meaning, unstated causation, a prose invented fact) needs a live model. |
| `clustering` | Partly | The title-similarity fallback (`cluster_by_title`) is deterministic and always scored. The real path — the model proposing groups — needs a live model. |
| `neutrality` | No | A wording heuristic (loaded/opinion language) over fixture text. Covers CLAUDE.md's "neutral wording" half only; source-spectrum balance is a `config/sources.yaml` curation property, not something one story's text can measure. |
| `groundedness` | Yes | Skipped. Needs a real Writer + Fact-checker run; there's no deterministic substitute for "share of claims supported." |
| `tag_accuracy` | Yes | Skipped. Measures how many of the *model's proposed* tags survive `validate_draft`'s taxonomy/grounding checks — the checks themselves already have unit tests and can't produce a meaningful "accuracy" number without something proposing tags to check. |

A `SKIP` is not a `FAIL`: it means a dependency this eval genuinely needs
is unavailable, not that anything regressed. The run's exit code only
reflects `FAIL`.

## Datasets

`evals/datasets/` holds every fixture: synthetic articles, planted-error
story variants, labelled clustering pairs, neutrality passages. All of it
is invented for this project — CLAUDE.md's public-repo hygiene rule: "test
fixtures and eval datasets must not contain full copyrighted articles."
Nothing here should ever be replaced with a real scraped article.

## What's genuinely untested here

The deterministic tiers above have real, current scores (see
`docs/BACKLOG.md` for the exact numbers, including the measured — not
assumed — 80% pairwise accuracy of the title-only clustering fallback on
paraphrased duplicate headlines). The LLM-dependent tiers are fully built
and ready to run the moment the gateway blocker is resolved, but have never
scored a real result in this environment. Run `uv run python -m evals.run`
again once that's fixed and update the numbers here and in the backlog.
