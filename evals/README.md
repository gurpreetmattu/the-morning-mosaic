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

## LLM-dependent tiers: now scored for real (2026-09-29)

The gateway blocker is resolved (Groq, plus Cloudflare as the Fact-checker's
pinned secondary gateway), so every tier above ran for real, repeatedly, for
the first time. See `docs/BACKLOG.md`'s "model choices are unvalidated
hypotheses" Done entry for the full writeup — summary: `tag_accuracy` and
`clustering.full_pipeline` scored 1.00 consistently across 8 live runs.
`groundedness` did not: 0.55–0.90 across 8 runs (mean ≈0.75, threshold 0.90),
7 of 8 runs failing the eval's own bar. Root-caused, not just measured — a
real mix of causes, not one bug:
- The pinned Fact-checker model (`@cf/meta/llama-3.3-70b-instruct-fp8-fast`,
  Cloudflare) occasionally returns malformed JSON. `FactChecker.check()`
  fails closed on this exactly as designed ("If it cannot run, nothing is
  verified, so every element fails rather than passing by default") — this
  inflates the *raw* groundedness score's failure count without reflecting
  any actual ungrounded claim.
- Some claims are marked `partial` over a defensible but arguably
  over-strict paraphrase distinction (e.g. "price growth" flagged against a
  passage that says "inflation").
- The real production path is `write_and_verify`'s retry loop (max 2
  retries), which this eval deliberately does not use — it measures one raw
  pass, on purpose, since that's what CLAUDE.md's "share of claims
  supported" asks for. A separate check confirmed the retry loop does
  recover the JSON-decode failures most of the time, but not always: across
  10 real end-to-end attempts (2 fixture stories × 5 rounds) through the
  actual retry loop, **2 were correctly dropped even after exhausting
  retries** — the safety net working as intended, not silently publishing,
  but a real, non-trivial "quiet news day" rate under today's pinned models.

This is exactly the kind of gap CLAUDE.md's eval requirement exists to
surface before trusting a model choice.

## Follow-up: the malformed-JSON retry (2026-09-29, same day)

Implemented the first of the three options above — `LlmClient` itself now
retries a malformed response under `json_object=True` (see
`docs/BACKLOG.md`'s Done entry for the full design: this moved from a
Fact-checker-only fix to the client layer once a diagnostic showed the
*Writer*, on a completely different pinned model, has the identical failure
shape). Re-measured live: **15 more runs, 10 passing (67%) versus 1 of 8
(12.5%) before** — a real improvement. But 2 of those 15 scored
catastrophically (0.00, 0.18), and chasing down why surfaced something more
important than the eval result itself: repeated live testing had quietly
burned through Groq's real daily token quota (confirmed via the raw
`LlmHttpError` — `openai/gpt-oss-20b` at 199,714/200,000 TPD), which is also
the Fact-checker's `availability_fallback_model` for when Cloudflare has a
bad moment. Testing stopped there rather than continuing to retry into an
exhausted provider and produce more noise.

So: the fix is real and correctly implemented (unit-tested at the client
layer, `test_llm_client.py`), the pass-rate improvement is real, and the two
remaining bad runs are **unattributed** — genuine remaining quality issues,
quota-exhaustion artifacts from the same investigation, or both. Re-run
`uv run python -m evals.run` a further several times once quota resets to
find out, rather than trust either explanation without checking. The
paraphrase-strictness false positives from the first measurement are
untouched by this fix and still real. Deciding whether to also adjust the
Fact-checker's paraphrase tolerance or pin a different model remains a real
decision with its own trade-offs, left to the owner.
