#!/usr/bin/env python
"""Run the capability classifier over work items that need it.

    python scripts/classify.py --limit 50

Intended to run on a schedule (Azure Container App job / cron). Safe to re-run:
human-reviewed classifications are never overwritten.
"""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy.orm import Session  # noqa: E402

from app.classification.classifier import CapabilityClassifier  # noqa: E402
from app.database.connection import read_engine  # noqa: E402

logging.basicConfig(level="INFO", format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with Session(read_engine) as session:
        classifier = CapabilityClassifier(session)
        if args.dry_run:
            pending = classifier.repo.work_items_needing_classification(limit=args.limit)
            for row in pending:
                print(f"{row['work_item_id']}\t{row['title']}")
            print(f"{len(pending)} work item(s) would be classified")
            return 0

        results = classifier.classify_pending(limit=args.limit)

    persisted = [r for r in results if r.is_usable]
    low = [r for r in persisted if r.is_low_confidence]
    skipped = [r for r in results if not r.is_usable]

    print(f"classified: {len(persisted)}  low-confidence: {len(low)}  skipped: {len(skipped)}")
    for r in skipped:
        print(f"  skipped {r.work_item_id}: {r.rejected_reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
