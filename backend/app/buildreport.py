"""Read-only report on a day's build: did it run, what did it publish, what did it cost.

    uv run python -m app.buildreport                     # today's edition (IST)
    uv run python -m app.buildreport --date 2026-10-02

Reads `pipeline_runs`, `edition_*`, `llm_calls` and `deliveries`; writes nothing.
Only runs that STARTED on the edition date (IST) are counted, so older runs that happened
to target the same date (dev tests, a manual rerun the night before) do not skew the totals.
Meant for the morning after a scheduled build: stories per genre, how long it took,
whether free-tier quotas ran out, and what the day would have cost on paid tiers.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import date

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.clock import IST, now_utc
from app.db.engine import get_engine

# $ per 1M tokens (input, output), from the providers' pricing pages, 2026-10-01.
# Free tiers bill nothing; this is what the same tokens would cost on a paid plan.
PRICES: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-20b": (0.075, 0.30),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "qwen/qwen3.8-27b": (0.80, 4.00),
    "@cf/meta/llama-3.3-70b-instruct-fp8-fast": (0.293, 2.253),
    "gemini-flash-lite-latest": (0.30, 2.50),
}


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Paid-tier price of these tokens; 0.0 for a model we have no price for."""
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def classify_error(error: str | None) -> str:
    """Bucket an `llm_calls.error` into the reason that matters when reading a build."""
    if not error:
        return "ok"
    lowered = error.lower()
    if "neurons" in lowered:
        return "quota: Cloudflare daily neurons"
    if "429" in lowered and "quota" in lowered:
        return "quota: daily/billing limit (HTTP 429)"
    if "429" in lowered and ("rate limit" in lowered or "tokens per" in lowered):
        return "rate limit: per-minute/day tokens (HTTP 429)"
    if "429" in lowered:
        return "HTTP 429 (other)"
    if "413" in lowered:
        return "request too large (HTTP 413)"
    if re.search(r"\b5\d\d\b", lowered):
        return "provider error (HTTP 5xx)"
    if "not valid json" in lowered or "failed to validate json" in lowered:
        return "model returned invalid JSON"
    return "other"


def _fmt_dt(value: object) -> str:
    if value is None:
        return "-"
    return (
        value.astimezone(IST).strftime("%H:%M:%S IST")
        if hasattr(value, "astimezone")
        else str(value)
    )


def _pairs(counts: object) -> str:
    if not isinstance(counts, dict) or not counts:
        return "none"
    return ", ".join(f"{key} {value}" for key, value in counts.items())


def format_genre_diagnostics(genre: str, d: dict[str, object]) -> list[str]:
    """Two readable lines for one genre from its saved `GenreDiagnostics`."""
    fallback = d.get("used_fallback_clustering")
    clustering = "not reached" if fallback is None else ("FALLBACK" if fallback else "model")
    more = ", asked for more coverage" if d.get("requested_more_coverage") else ""
    return [
        f"     {genre}: collected {d.get('collected', 0)} ({_pairs(d.get('articles_by_source'))})"
        f"; dropped at collection: {_pairs(d.get('collector_drops'))}",
        f"        clusters {d.get('clusters', 0)} (clustering: {clustering}{more})"
        f" -> pooled {d.get('pooled', 0)}; pool drops: {_pairs(d.get('pool_drops'))}"
        f" -> attempted {d.get('attempted', 0)}, verified {d.get('verified', 0)}"
        f" in {d.get('write_cycles', 0)} write cycles; abandoned: {_pairs(d.get('abandoned'))}",
    ]


def build_runs(conn: Connection, edition_date: date) -> list[dict[str, object]]:
    rows = conn.execute(
        text(
            """select id, job, status, started_at, finished_at, deadline_at, detail
               from pipeline_runs
               where edition_date = :d and job in ('build', 'late_update')
                 and (started_at at time zone 'Asia/Kolkata')::date = :d
               order by started_at"""
        ),
        {"d": edition_date},
    ).mappings()
    return [dict(row) for row in rows]


def report(conn: Connection, edition_date: date) -> str:
    lines: list[str] = [
        f"BUILD REPORT for edition {edition_date}"
        f"  (generated {now_utc().astimezone(IST):%Y-%m-%d %H:%M IST})",
        "",
    ]
    runs = build_runs(conn, edition_date)
    if not runs:
        lines.append("No build or late-update run is recorded for this date.")
        lines.append(
            "(The scheduled build starts 04:15 IST; if it is later than that, it did not start.)"
        )
        return "\n".join(lines)

    lines.append("RUNS")
    for run in runs:
        started, finished = run["started_at"], run["finished_at"]
        minutes = (
            f"{(finished - started).total_seconds() / 60:.1f} min"  # type: ignore[operator]
            if started and finished
            else "still running or never finished"
        )
        detail = run["detail"] or {}
        error = detail.get("error") if isinstance(detail, dict) else None
        lines.append(
            f"  {run['job']:11s} {run['status']!s:10s} {_fmt_dt(started)} -> {_fmt_dt(finished)}"
            f"  ({minutes}; deadline {_fmt_dt(run['deadline_at'])})"
            + (f"  ERROR: {error}" if error else "")
        )

    lines += ["", "WHY EACH GENRE CAME OUT AS IT DID"]
    explained = False
    for run in runs:
        detail = run["detail"]
        genres = detail.get("genres") if isinstance(detail, dict) else None
        if not isinstance(genres, dict) or not genres:
            continue
        explained = True
        lines.append(f"  {run['job']} {_fmt_dt(run['started_at'])}")
        for genre, diag in sorted(genres.items()):
            if isinstance(diag, dict):
                lines.extend(format_genre_diagnostics(genre, diag))
    if not explained:
        lines.append("  not recorded (runs before 2026-10-02 did not save diagnostics)")

    lines += ["", "PUBLISHED"]
    revisions = (
        conn.execute(
            text(
                """select v.id, v.revision, v.reason, v.published_at from edition_revisions v
                join editions e on e.id = v.edition_id
                where e.edition_date = :d order by v.revision"""
            ),
            {"d": edition_date},
        )
        .mappings()
        .all()
    )
    if not revisions:
        lines.append("  NOTHING published for this date.")
    for rev in revisions:
        lines.append(
            f"  revision {rev['revision']} ({rev['reason']}) at {_fmt_dt(rev['published_at'])}"
        )
        for sec in conn.execute(
            text(
                "select genre, status, story_count from edition_sections "
                "where revision_id = :r order by genre"
            ),
            {"r": rev["id"]},
        ).mappings():
            lines.append(
                f"     {sec['genre']:11s} {sec['status']!s:10s} {sec['story_count']} stories"
            )

    run_ids = [run["id"] for run in runs]
    lines += ["", "LLM CALLS (all runs above)"]
    rows = (
        conn.execute(
            text(
                """select agent, model, status, error, prompt_tokens, completion_tokens
               from llm_calls where pipeline_run_id = any(:ids)"""
            ),
            {"ids": run_ids},
        )
        .mappings()
        .all()
    )
    if not rows:
        lines.append("  none recorded")
    else:
        ok: Counter[tuple[str, str]] = Counter()
        tokens: dict[tuple[str, str], list[int]] = {}
        failures: Counter[tuple[str, str]] = Counter()
        for row in rows:
            key = (row["agent"], row["model"])
            if row["status"] == "ok":
                ok[key] += 1
                bucket = tokens.setdefault(key, [0, 0])
                bucket[0] += row["prompt_tokens"] or 0
                bucket[1] += row["completion_tokens"] or 0
            else:
                failures[(f"{row['agent']} / {row['model']}", classify_error(row["error"]))] += 1
        total_cost = 0.0
        total_in = total_out = 0
        for (agent, model), count in sorted(ok.items()):
            tin, tout = tokens[(agent, model)]
            total_in, total_out = total_in + tin, total_out + tout
            total_cost += cost_usd(model, tin, tout)
            lines.append(
                f"  ok   {agent:12s} {model:42s} {count:4d} calls {tin:8,d} in {tout:7,d} out"
            )
        lines.append(
            f"  tokens billed on a paid plan: {total_in:,} in / {total_out:,} out"
            f" = ${total_cost:.3f}  (free tiers: $0)"
        )
        if failures:
            lines.append("  FAILED calls (not billed):")
            for (route, reason), count in failures.most_common():
                lines.append(f"     {count:5d}  {route:60s} {reason}")
        else:
            lines.append("  no failed calls")

    lines += ["", "DELIVERIES"]
    deliveries = conn.execute(
        text(
            "select type, status, count(*) n from deliveries "
            "where edition_date = :d group by 1, 2 order by 1, 2"
        ),
        {"d": edition_date},
    ).all()
    lines += [f"  {t:15s} {s:10s} {n}" for t, s, n in deliveries] or [
        "  no delivery rows for this date"
    ]
    delivery_runs = (
        conn.execute(
            text(
                "select status, started_at, detail from pipeline_runs "
                "where edition_date = :d and job = 'delivery' order by started_at"
            ),
            {"d": edition_date},
        )
        .mappings()
        .all()
    )
    for drun in delivery_runs:
        lines.append(
            f"  delivery run {drun['status']} {_fmt_dt(drun['started_at'])} {drun['detail']}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only report on a day's build.")
    parser.add_argument(
        "--date", type=date.fromisoformat, default=None, help="edition date (IST); default today"
    )
    args = parser.parse_args(argv)
    edition_date = args.date or now_utc().astimezone(IST).date()
    with get_engine().connect() as conn:
        print(report(conn, edition_date))
    return 0


if __name__ == "__main__":
    sys.exit(main())
