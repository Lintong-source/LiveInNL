#!/usr/bin/env python3
"""Fail safely when Expatus production configuration is incomplete.

The script never prints secret values. Run it with the same environment that
will be used for the production deployment.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    """Load a local operator file without importing Flask or printing values."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, raw_value = line.split("=", 1)
        name = name.strip()
        if name and name not in os.environ:
            os.environ[name] = raw_value.strip().strip('"').strip("'")


def flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> int:
    load_env_file(ROOT / ".env")
    errors: list[str] = []
    warnings: list[str] = []

    exact = {
        "APP_ENV": "production",
        "BASE_URL": "https://www.expatus.nl",
        "DATABASE_BACKEND": "turso",
        "ENFORCE_CANONICAL_HOST": "1",
        "COOKIE_SECURE": "1",
        "FLASK_DEBUG": "0",
        "DEMO_MODE": "0",
        "DEV_SHOW_VERIFICATION_CODE": "0",
    }
    for name, expected in exact.items():
        if os.getenv(name, "").strip().lower() != expected.lower():
            errors.append(f"{name} must be {expected}")

    secret = os.getenv("SECRET_KEY", "")
    admin_password = os.getenv("ADMIN_PASSWORD", "")
    if len(secret) < 32 or "local-development" in secret.lower():
        errors.append("SECRET_KEY must be a new random value of at least 32 characters")
    if len(admin_password) < 20 or admin_password == secret or "local-admin" in admin_password.lower():
        errors.append("ADMIN_PASSWORD must be an independent value of at least 20 characters")

    for name in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "SMTP_HOST", "SMTP_FROM"):
        if not os.getenv(name, "").strip():
            errors.append(f"{name} is required")
    if os.getenv("SMTP_USERNAME", "").strip() and not os.getenv("SMTP_PASSWORD", "").strip():
        errors.append("SMTP_PASSWORD is required when SMTP_USERNAME is configured")

    controller = os.getenv("PRIVACY_CONTROLLER_NAME", "").strip()
    privacy_email = os.getenv("PRIVACY_CONTACT_EMAIL", "").strip()
    hosting_region = os.getenv("HOSTING_REGION", "").strip()
    database_region = os.getenv("DATABASE_REGION", "").strip()
    if not controller or controller in {"Expatus 网站运营者", "Expatus 本地测试"}:
        errors.append("PRIVACY_CONTROLLER_NAME must identify the real controller")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", privacy_email):
        errors.append("PRIVACY_CONTACT_EMAIL must be a working email address")
    for name, value in (("HOSTING_REGION", hosting_region), ("DATABASE_REGION", database_region)):
        if not value or "核实" in value or "为准" in value:
            errors.append(f"{name} must contain a verified infrastructure fact")

    for name in ("LOG_RETENTION_DAYS", "MESSAGE_RETENTION_DAYS", "STRATEGY_RETENTION_DAYS"):
        try:
            days = int(os.getenv(name, ""))
            if not 1 <= days <= 3650:
                raise ValueError
        except ValueError:
            errors.append(f"{name} must be an integer from 1 to 3650")

    if flag("ANALYTICS_ENABLED"):
        measurement_id = os.getenv("GA_MEASUREMENT_ID", "").strip()
        if not re.fullmatch(r"G-[A-Z0-9]+", measurement_id):
            errors.append("GA_MEASUREMENT_ID is invalid while analytics is enabled")
    else:
        warnings.append("Analytics remains disabled; this is safe for Preview and initial smoke tests")

    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    for dependency in ("flask", "libsql", "turso_serverless"):
        if dependency not in requirements:
            errors.append(f"requirements.txt is missing {dependency}")

    vercel = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    redirects = vercel.get("redirects", [])
    if not any(
        item.get("destination") == "https://www.expatus.nl/:path*"
        and item.get("permanent") is True
        for item in redirects
    ):
        errors.append("vercel.json must permanently redirect the apex domain to www")

    databases = list(ROOT.rglob("*.db")) + list(ROOT.rglob("*.sqlite"))
    if databases:
        errors.append("Release directory contains a local database file")

    print("Expatus v1.3 production preflight")
    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print(f"Preflight failed with {len(errors)} blocking item(s). Secret values were not printed.")
        return 1
    print("PASS: production configuration and release structure are ready for deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
