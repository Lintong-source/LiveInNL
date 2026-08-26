"""Centralized UTC clock to keep database timestamps consistent."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
