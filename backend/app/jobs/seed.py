"""Seed reference tables from /config.

A deploy-time task, not one of the scheduled Cloud Run jobs. Safe to rerun.

    uv run python -m app.jobs.seed [--dry-run]
"""

from __future__ import annotations

import argparse
import sys

from app.db.engine import dispose_engine, session_scope
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
        with session_scope() as session:
            summary = seed_all(session)
            print(summary.cities.describe("cities"))
            print(summary.sources.describe("sources"))
            if args.dry_run:
                session.rollback()
                print("dry run: rolled back")
    finally:
        dispose_engine()

    return 0


if __name__ == "__main__":
    sys.exit(main())
