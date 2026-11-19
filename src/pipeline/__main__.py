"""CLI entry point.

Examples:
    python -m pipeline ingest --source all --date 2026-11-15 --mock
    python -m pipeline freshness --today 2026-11-16
    python -m pipeline reconcile --threshold 0.99
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from .checks import check_freshness, check_reconciliation
from .config import Settings
from .logging_utils import log
from .runner import RUNNERS
from .warehouse import get_warehouse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Extract one business date into the raw layer")
    ingest.add_argument("--source", choices=[*RUNNERS, "all"], default="all")
    ingest.add_argument("--date", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    ingest.add_argument("--days", type=int, default=1, help="Backfill N days ending at --date")
    ingest.add_argument("--mock", action="store_true", help="Use bundled sample data instead of live sources")

    fresh = sub.add_parser("freshness", help="Fail if any source is stale")
    fresh.add_argument("--today", type=date.fromisoformat, default=date.today())

    recon = sub.add_parser("reconcile", help="Fail if store/date match rate is below threshold")
    recon.add_argument("--threshold", type=float, default=0.99)

    args = parser.parse_args(argv)
    settings = Settings.from_env()
    wh = get_warehouse(settings)

    if args.command == "ingest":
        sources = list(RUNNERS) if args.source == "all" else [args.source]
        failed = False
        for offset in range(args.days - 1, -1, -1):
            day = args.date - timedelta(days=offset)
            for name in sources:
                try:
                    RUNNERS[name](settings, wh, day, mock=args.mock)
                except Exception as exc:  # one failing source must not block the others
                    failed = True
                    log("ingest_failed", "ERROR", source=name, business_date=day, error=repr(exc))
        return 1 if failed else 0

    if args.command == "freshness":
        results = check_freshness(wh, args.today, settings.freshness_max_lag_days)
        return 0 if all(results.values()) else 1

    if args.command == "reconcile":
        return 0 if check_reconciliation(wh, args.threshold) >= args.threshold else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
