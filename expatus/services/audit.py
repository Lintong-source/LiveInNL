"""Minimal operational event log; deliberately excludes passwords and raw IPs."""

from __future__ import annotations

import json

from flask import g, request

from expatus.database import get_db
from expatus.services.clock import utcnow
from expatus.services.security import actor_hash


ALLOWED_EVENT_TYPES = {
    "register_started",
    "register_completed",
    "login_success",
    "login_failed",
    "logout",
    "password_reset",
    "strategy_generated",
    "property_created",
    "property_updated",
    "property_deleted",
    "favorite_updated",
    "message_submitted",
    "case_submitted",
    "admin_login_success",
    "admin_login_failed",
    "account_exported",
    "account_deleted",
    "privacy_acknowledged",
}


def record(event_type: str, *, user_id=None, outcome="success", subject="", details=None) -> None:
    if event_type not in ALLOWED_EVENT_TYPES:
        raise ValueError(f"Unsupported audit event: {event_type}")
    if user_id is None and getattr(g, "user", None):
        user_id = g.user["id"]
    safe_details = details or {}
    # Never place submitted messages, passwords, verification codes or profile payloads in logs.
    for forbidden in {"password", "password_hash", "verification_code", "code", "message"}:
        safe_details.pop(forbidden, None)
    get_db().execute(
        "INSERT INTO audit_events(user_id,event_type,outcome,subject,ip_hash,user_agent,details_json,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (
            user_id,
            event_type,
            outcome,
            str(subject or "")[:120],
            actor_hash(),
            request.user_agent.string[:180],
            json.dumps(safe_details, ensure_ascii=False, separators=(",", ":")),
            utcnow().isoformat(),
        ),
    )
    get_db().commit()
