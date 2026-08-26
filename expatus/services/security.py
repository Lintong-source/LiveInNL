"""Session, CSRF, canonical-host and abuse-prevention helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from functools import wraps

from flask import abort, current_app, g, jsonify, redirect, request, session, url_for

from expatus.database import get_db
from expatus.services.clock import utcnow
from expatus.services.validation import safe_next


def csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def actor_hash() -> str:
    """Hash the client IP instead of retaining raw addresses in audit tables."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    address = (forwarded.split(",", 1)[0].strip() if forwarded else request.remote_addr) or "unknown"
    material = f"{current_app.secret_key}:actor:{address}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def check_rate_limit(bucket: str, *, maximum: int, seconds: int, discriminator: str = "") -> bool:
    identifier = actor_hash()
    if discriminator:
        identifier = hashlib.sha256(f"{identifier}:{discriminator.lower()}".encode()).hexdigest()
    cutoff = (utcnow() - timedelta(seconds=seconds)).isoformat()
    connection = get_db()
    count = connection.execute(
        "SELECT COUNT(*) AS total FROM rate_limit_events "
        "WHERE bucket=? AND actor_hash=? AND created_at>=?",
        (bucket, identifier, cutoff),
    ).fetchone()["total"]
    if count >= maximum:
        return False
    connection.execute(
        "INSERT INTO rate_limit_events(bucket,actor_hash,created_at) VALUES(?,?,?)",
        (bucket, identifier, utcnow().isoformat()),
    )
    connection.commit()
    return True


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            target = request.full_path if request.query_string else request.path
            return redirect(url_for("pages.auth_page", next=safe_next(target)))
        return view(*args, **kwargs)

    return wrapper


def api_login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            return jsonify(
                ok=False,
                error="请先登录。",
                login_url=url_for("pages.auth_page", next=safe_next(request.referrer or "/")),
            ), 401
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin.login", next=request.path))
        return view(*args, **kwargs)

    return wrapper


def before_request():
    settings = current_app.config["EXPATUS_SETTINGS"]
    host = request.host.split(":", 1)[0].lower()
    if settings.enforce_canonical_host and host == "expatus.nl":
        destination = settings.base_url + request.full_path
        return redirect(destination.rstrip("?"), code=301)

    g.user = None
    user_id = session.get("user_id")
    if user_id:
        g.user = get_db().execute(
            "SELECT * FROM users WHERE id=? AND deleted_at IS NULL", (user_id,)
        ).fetchone()
        if g.user is None:
            session.pop("user_id", None)

    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("_csrf") or ""
        expected = session.get("_csrf") or ""
        if not expected or not secrets.compare_digest(str(supplied), str(expected)):
            if request.path.startswith("/api/"):
                return jsonify(ok=False, error="页面验证信息已失效，请刷新页面后重试。"), 400
            abort(400)


def after_request(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.path.startswith(
        ("/admin", "/workspace", "/progress", "/favorites", "/account", "/auth", "/api/account", "/api/properties")
    ):
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        response.headers.setdefault("Cache-Control", "private, no-store")
    return response
