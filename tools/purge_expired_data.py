#!/usr/bin/env python3
"""Preview or apply configured GDPR-oriented database retention periods."""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from expatus import create_app
from expatus.database import get_db
from expatus.services.clock import utcnow


def retention_targets(settings):
    now = utcnow()
    return [
        ("audit_events", "created_at", now - timedelta(days=settings.log_retention_days)),
        ("rate_limit_events", "created_at", now - timedelta(days=2)),
        ("strategy_generations", "created_at", now - timedelta(days=settings.strategy_retention_days)),
        ("contact_messages", "created_at", now - timedelta(days=settings.message_retention_days)),
        ("case_submissions", "created_at", now - timedelta(days=settings.message_retention_days)),
        ("pending_registrations", "updated_at", now - timedelta(days=2)),
        ("verification_codes", "expires_at", now - timedelta(days=2)),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete expired rows; default is preview only.")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        settings = app.config["EXPATUS_SETTINGS"]
        connection = get_db()
        total = 0
        for table, column, cutoff in retention_targets(settings):
            count = connection.execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE {column}<?", (cutoff.isoformat(),)
            ).fetchone()["total"]
            total += count
            if args.apply and count:
                connection.execute(f"DELETE FROM {table} WHERE {column}<?", (cutoff.isoformat(),))
            print(f"{table}: {count} expired rows")
        if args.apply:
            connection.commit()
        print(f"{'Deleted' if args.apply else 'Previewed'} {total} expired rows.")
        if not args.apply:
            print("Run again with --apply only when you intend to delete these rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
