"""Environment-backed application configuration.

Local development deliberately defaults to SQLite and disabled analytics.
Production can opt into Turso, HTTPS cookies, canonical redirects and GA4.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    """Read a small .env file without adding another runtime dependency."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = raw_value.strip().strip('"').strip("'")


def env_flag(name: str, default: bool = False) -> bool:
    return os.getenv(name, "1" if default else "0").strip().lower() in {
        "1", "true", "yes", "on",
    }


def env_value(name: str, *fallback_names: str, default: str = "") -> str:
    """Return the first configured value, allowing provider-prefixed aliases."""
    for candidate in (name, *fallback_names):
        value = os.getenv(candidate)
        if value is not None and value.strip():
            return value.strip()
    return default


@dataclass(frozen=True)
class Settings:
    environment: str
    secret_key: str
    base_url: str
    database_path: Path
    database_backend: str
    turso_database_url: str
    turso_auth_token: str
    demo_mode: bool
    show_verification_code: bool
    admin_password: str
    analytics_enabled: bool
    analytics_measurement_id: str
    enforce_canonical_host: bool
    cookie_secure: bool
    controller_name: str
    controller_email: str
    controller_country: str
    hosting_region: str
    database_region: str
    privacy_policy_version: str
    log_retention_days: int
    message_retention_days: int
    strategy_retention_days: int

    @property
    def canonical_host(self) -> str:
        return urlparse(self.base_url).netloc

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def load_settings(overrides: dict | None = None) -> Settings:
    load_env_file(PROJECT_ROOT / ".env")
    environment = os.getenv("APP_ENV", "development").strip().lower()
    # Vercel Preview has a read-only project filesystem. Use its writable
    # temporary directory unless an explicit database path was configured.
    default_database_path = PROJECT_ROOT / "data" / "expatus-local.db"
    if os.getenv("VERCEL_ENV", "").strip().lower() == "preview":
        default_database_path = Path("/tmp/expatus-preview.db")

    database_path = Path(os.getenv("EXPATUS_DB", str(default_database_path)))
    if not database_path.is_absolute():
        database_path = PROJECT_ROOT / database_path
    settings = Settings(
        environment=environment,
        secret_key=os.getenv("SECRET_KEY", "local-development-only-change-before-production"),
        base_url=os.getenv("BASE_URL", "https://www.expatus.nl").rstrip("/"),
        database_path=database_path,
        database_backend=os.getenv("DATABASE_BACKEND", "sqlite").strip().lower(),
        # Vercel Marketplace may prefix integration credentials with the
        # resource name. Keep the generic names primary and support the
        # existing Expatus integration aliases without duplicating secrets.
        turso_database_url=env_value(
            "TURSO_DATABASE_URL", "expatus_TURSO_DATABASE_URL"
        ),
        turso_auth_token=env_value(
            "TURSO_AUTH_TOKEN", "expatus_TURSO_AUTH_TOKEN"
        ),
        demo_mode=env_flag("DEMO_MODE", environment != "production"),
        show_verification_code=env_flag("DEV_SHOW_VERIFICATION_CODE", environment != "production"),
        admin_password=os.getenv("ADMIN_PASSWORD", "local-admin-change-me" if environment != "production" else ""),
        analytics_enabled=env_flag("ANALYTICS_ENABLED", False),
        analytics_measurement_id=os.getenv("GA_MEASUREMENT_ID", "G-FZPQP950J0").strip(),
        enforce_canonical_host=env_flag("ENFORCE_CANONICAL_HOST", environment == "production"),
        cookie_secure=env_flag("COOKIE_SECURE", environment == "production"),
        controller_name=os.getenv("PRIVACY_CONTROLLER_NAME", "Expatus 网站运营者"),
        controller_email=os.getenv("PRIVACY_CONTACT_EMAIL", "privacy@expatus.nl"),
        controller_country=os.getenv("PRIVACY_CONTROLLER_COUNTRY", "荷兰"),
        hosting_region=os.getenv("HOSTING_REGION", "以 Vercel 项目实际部署区域为准；上线前核实并填写"),
        database_region=os.getenv("DATABASE_REGION", "以 Turso 数据库实际区域为准；上线前核实并填写"),
        privacy_policy_version=os.getenv("PRIVACY_POLICY_VERSION", "2026-08-25"),
        log_retention_days=int(os.getenv("LOG_RETENTION_DAYS", "90")),
        message_retention_days=int(os.getenv("MESSAGE_RETENTION_DAYS", "365")),
        strategy_retention_days=int(os.getenv("STRATEGY_RETENTION_DAYS", "180")),
    )
    if overrides:
        from dataclasses import replace

        settings = replace(settings, **overrides)
    if settings.is_production and settings.secret_key.startswith("local-development"):
        raise RuntimeError("Production requires a strong SECRET_KEY.")
    if settings.database_backend not in {"sqlite", "turso"}:
        raise RuntimeError("DATABASE_BACKEND must be sqlite or turso.")
    if settings.database_backend == "turso" and not (
        settings.turso_database_url and settings.turso_auth_token
    ):
        raise RuntimeError("Turso requires TURSO_DATABASE_URL and TURSO_AUTH_TOKEN.")
    return settings
