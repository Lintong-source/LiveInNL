"""Queries for accounts, pending registrations and one-time verification codes."""

from __future__ import annotations

from expatus.database import get_db
from expatus.services.clock import utcnow


def find_by_email(email: str):
    return get_db().execute(
        "SELECT * FROM users WHERE email=? AND deleted_at IS NULL", (email,)
    ).fetchone()


def find_by_id(user_id: int):
    return get_db().execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def save_pending(email: str, password_hash: str, *, policy_version: str) -> None:
    now = utcnow().isoformat()
    get_db().execute(
        "INSERT INTO pending_registrations(email,password_hash,created_at,updated_at,"
        "privacy_acknowledged_at,privacy_policy_version) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash,"
        "updated_at=excluded.updated_at,privacy_acknowledged_at=excluded.privacy_acknowledged_at,"
        "privacy_policy_version=excluded.privacy_policy_version",
        (email, password_hash, now, now, now, policy_version),
    )
    get_db().commit()


def pending(email: str):
    return get_db().execute("SELECT * FROM pending_registrations WHERE email=?", (email,)).fetchone()


def activate_pending(email: str) -> int:
    item = pending(email)
    if item is None:
        raise ValueError("注册信息已失效，请重新开始。")
    now = utcnow().isoformat()
    cursor = get_db().execute(
        "INSERT INTO users(email,password_hash,verified_at,created_at,"
        "privacy_acknowledged_at,privacy_policy_version,last_login_at) VALUES(?,?,?,?,?,?,?)",
        (
            email,
            item["password_hash"],
            now,
            now,
            item["privacy_acknowledged_at"],
            item["privacy_policy_version"],
            now,
        ),
    )
    get_db().execute("DELETE FROM pending_registrations WHERE email=?", (email,))
    get_db().commit()
    return cursor.lastrowid


def set_last_login(user_id: int) -> None:
    get_db().execute("UPDATE users SET last_login_at=? WHERE id=?", (utcnow().isoformat(), user_id))
    get_db().commit()


def acknowledge_privacy(user_id: int, policy_version: str) -> None:
    """Record when a pre-existing account reviewed the current privacy notice."""
    get_db().execute(
        "UPDATE users SET privacy_acknowledged_at=?,privacy_policy_version=? WHERE id=?",
        (utcnow().isoformat(), policy_version, user_id),
    )
    get_db().commit()


def set_password(user_id: int, password_hash: str) -> None:
    get_db().execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))
    get_db().commit()


def list_users(limit: int = 200):
    return get_db().execute(
        "SELECT u.id,u.email,u.verified_at,u.created_at,u.last_login_at,"
        "u.privacy_acknowledged_at,u.privacy_policy_version,"
        "(SELECT COUNT(*) FROM properties p WHERE p.user_id=u.id) AS property_count,"
        "(SELECT COUNT(*) FROM strategy_generations s WHERE s.user_id=u.id) AS strategy_count "
        "FROM users u WHERE u.deleted_at IS NULL ORDER BY u.created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
