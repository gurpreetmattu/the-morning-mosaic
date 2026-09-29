"""Seed reference tables from /config.

A deploy-time task, not one of the scheduled Cloud Run jobs. Safe to rerun.

Only needs DATABASE_URL, not every other variable the rest of the app
requires (mail, LLM, tokens, ...) — this job never touches any of them. Uses
SeedSettings/get_seed_engine (see app/config/settings.py and
app/db/engine.py) rather than the shared Settings/get_engine every other job
uses, so running this in dev doesn't require configuring things it never
reads.

    uv run python -m app.jobs.seed [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

from app.db.engine import dispose_seed_engine, seed_session_scope
from app.db.seed import seed_all


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would change, then roll back",
    )
    args = parser.parse_args(argv)

    try:
        with seed_session_scope() as session:
            summary = seed_all(session)
            print(summary.cities.describe("cities"))
            print(summary.sources.describe("sources"))
            if args.dry_run:
                session.rollback()
                print("dry run: rolled back")
    finally:
        dispose_seed_engine()

    return 0


if __name__ == "__main__":
    sys.exit(main())
