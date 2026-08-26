"""SQLite/Turso connections and additive, existing-data-safe migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash

from expatus.services.clock import utcnow


class CompatRow(dict):
    """Expose both dictionary keys and SQLite-style positional indices."""

    def __init__(self, columns, values):
        self._values = tuple(values)
        super().__init__(zip(columns, self._values))

    def __getitem__(self, key):
        return self._values[key] if isinstance(key, int) else super().__getitem__(key)


class CompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)

    @property
    def rowcount(self):
        return getattr(self._cursor, "rowcount", -1)

    def _convert(self, row):
        if row is None:
            return None
        if isinstance(row, dict):
            return CompatRow(list(row), list(row.values()))
        return CompatRow([column[0] for column in self._cursor.description or []], row)

    def fetchone(self):
        return self._convert(self._cursor.fetchone())

    def fetchall(self):
        return [self._convert(row) for row in self._cursor.fetchall()]


class RemoteConnection:
    """Keep repositories portable between Python sqlite3 and Turso clients."""

    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        return CompatCursor(self._connection.execute(sql, params))

    def executescript(self, script):
        statement = ""
        for line in script.splitlines():
            statement += line + "\n"
            if sqlite3.complete_statement(statement):
                if statement.strip():
                    self.execute(statement.strip())
                statement = ""
        if statement.strip():
            self.execute(statement.strip())
        return self

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        operation = getattr(self._connection, "rollback", None)
        if operation:
            return operation()

    def close(self):
        return self._connection.close()


def connect(settings):
    if settings.database_backend == "turso":
        if settings.turso_database_url.startswith("turso://"):
            import turso_serverless

            remote = turso_serverless.connect(
                settings.turso_database_url, auth_token=settings.turso_auth_token
            )
        else:
            import libsql

            remote = libsql.connect(
                database=settings.turso_database_url,
                auth_token=settings.turso_auth_token,
            )
        connection = RemoteConnection(remote)
    else:
        database_path = Path(settings.database_path)
        database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys=ON")
    except Exception:
        current_app.logger.warning("Database does not expose foreign-key PRAGMA")
    return connection


def get_db():
    if "expatus_db" not in g:
        g.expatus_db = connect(current_app.config["EXPATUS_SETTINGS"])
    return g.expatus_db


def close_db(_exception=None):
    connection = g.pop("expatus_db", None)
    if connection is not None:
        connection.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    verified_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    privacy_acknowledged_at TEXT,
    privacy_policy_version TEXT,
    last_login_at TEXT,
    deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS pending_registrations (
    email TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    privacy_acknowledged_at TEXT,
    privacy_policy_version TEXT
);
CREATE TABLE IF NOT EXISTS verification_codes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    purpose TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    used_at TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_codes_email_purpose
ON verification_codes(email, purpose, created_at DESC);
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    source TEXT,
    rent REAL,
    url TEXT,
    status TEXT NOT NULL DEFAULT '待处理',
    is_ended INTEGER NOT NULL DEFAULT 0,
    end_reason TEXT,
    ended_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_properties_user
ON properties(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS favorites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, platform)
);
CREATE TABLE IF NOT EXISTS case_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    city TEXT,
    contract_date TEXT,
    rental_ended TEXT,
    moveout_date TEXT,
    base_rent REAL,
    deposit REAL,
    issues_json TEXT NOT NULL,
    checkin_report TEXT,
    deduction_spec TEXT,
    description TEXT NOT NULL,
    email TEXT,
    wechat TEXT,
    contact_ok INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS contact_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    category TEXT NOT NULL,
    subject TEXT,
    message TEXT NOT NULL,
    email TEXT,
    wechat TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contact_messages_created
ON contact_messages(created_at DESC);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT 'success',
    subject TEXT,
    ip_hash TEXT,
    user_agent TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_events_type_time
ON audit_events(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_user_time
ON audit_events(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS strategy_generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    identity_type TEXT NOT NULL,
    city TEXT NOT NULL,
    move_date TEXT NOT NULL,
    home_type TEXT NOT NULL,
    budget INTEGER,
    income_type TEXT,
    student_registration TEXT,
    university_housing TEXT,
    area_flexibility TEXT,
    result_summary TEXT,
    engine_version TEXT,
    result_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_strategy_user_time
ON strategy_generations(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS rate_limit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bucket TEXT NOT NULL,
    actor_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rate_limit_lookup
ON rate_limit_events(bucket, actor_hash, created_at DESC);
"""


ADDITIVE_COLUMNS = {
    "users": {
        "password_hash": "TEXT",
        "privacy_acknowledged_at": "TEXT",
        "privacy_policy_version": "TEXT",
        "last_login_at": "TEXT",
        "deleted_at": "TEXT",
    },
    "pending_registrations": {
        "privacy_acknowledged_at": "TEXT",
        "privacy_policy_version": "TEXT",
    },
    "properties": {
        "is_ended": "INTEGER NOT NULL DEFAULT 0",
        "end_reason": "TEXT",
        "ended_at": "TEXT",
    },
    "strategy_generations": {
        "engine_version": "TEXT",
        "result_json": "TEXT",
    },
}


def migrate(connection, settings) -> None:
    """Only add missing structures; existing production rows remain untouched."""
    connection.executescript(SCHEMA)
    for table, columns in ADDITIVE_COLUMNS.items():
        present = {
            row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, definition in columns.items():
            if name not in present:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    for old, new in {
        "待联系": "待处理",
        "已联系": "已表达意向",
        "准备申请": "准备申请材料",
        "申请中": "已提交申请",
    }.items():
        connection.execute("UPDATE properties SET status=? WHERE status=?", (new, old))

    if settings.demo_mode and settings.database_backend == "sqlite":
        now = utcnow().isoformat()
        demo_email = "demo@expatus.test"
        existing = connection.execute(
            "SELECT id FROM users WHERE email=?", (demo_email,)
        ).fetchone()
        if existing is None:
            connection.execute(
                "INSERT INTO users(email,password_hash,verified_at,created_at,"
                "privacy_acknowledged_at,privacy_policy_version) VALUES(?,?,?,?,?,?)",
                (
                    demo_email,
                    generate_password_hash("expatus123"),
                    now,
                    now,
                    now,
                    settings.privacy_policy_version,
                ),
            )
    connection.commit()


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
    with app.app_context():
        connection = connect(app.config["EXPATUS_SETTINGS"])
        try:
            migrate(connection, app.config["EXPATUS_SETTINGS"])
        finally:
            connection.close()
