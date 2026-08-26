"""Small operations dashboard: accounts, logins, messages, cases and strategies."""

from __future__ import annotations

import csv
import io
import secrets
from datetime import timedelta

from flask import Blueprint, Response, current_app, redirect, render_template, request, session, url_for

from expatus.database import get_db
from expatus.repositories import strategies, submissions, users
from expatus.services import audit
from expatus.services.clock import utcnow
from expatus.services.security import admin_required, check_rate_limit, csrf_token
from expatus.services.validation import safe_next


blueprint = Blueprint("admin", __name__, url_prefix="/admin")


def _count(table: str, where: str = "", params=()) -> int:
    # Table names are fixed constants supplied only by this module.
    allowed = {"users", "audit_events", "strategy_generations", "contact_messages", "case_submissions", "properties"}
    if table not in allowed:
        raise ValueError("Unknown dashboard table")
    return get_db().execute(
        f"SELECT COUNT(*) AS total FROM {table}" + (f" WHERE {where}" if where else ""),
        params,
    ).fetchone()["total"]


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    settings = current_app.config["EXPATUS_SETTINGS"]
    configured = bool(settings.admin_password)
    error = None
    if request.method == "POST":
        if not check_rate_limit("admin_login", maximum=8, seconds=900):
            error = "尝试次数过多，请 15 分钟后再试。"
        elif configured and secrets.compare_digest(
            str(request.form.get("password") or ""), settings.admin_password
        ):
            session["admin_authenticated"] = True
            session.permanent = True
            csrf_token()
            audit.record("admin_login_success")
            return redirect(safe_next(request.form.get("next") or "/admin"))
        else:
            audit.record("admin_login_failed", outcome="denied")
            error = "后台密码不正确。"
    return render_template(
        "admin/login.html",
        error=error,
        configured=configured,
        next_url=safe_next(request.args.get("next") or request.form.get("next") or "/admin"),
    )


@blueprint.post("/logout")
def logout():
    session.pop("admin_authenticated", None)
    return redirect(url_for("admin.login"))


@blueprint.get("")
@blueprint.get("/")
@admin_required
def dashboard():
    day_ago = (utcnow() - timedelta(hours=24)).isoformat()
    week_ago = (utcnow() - timedelta(days=7)).isoformat()
    metrics = {
        "users": _count("users", "deleted_at IS NULL"),
        "new_users_week": _count("users", "created_at>=? AND deleted_at IS NULL", (week_ago,)),
        "logins_day": _count("audit_events", "event_type='login_success' AND created_at>=?", (day_ago,)),
        "failed_logins_day": _count("audit_events", "event_type='login_failed' AND created_at>=?", (day_ago,)),
        "strategies": _count("strategy_generations"),
        "strategies_week": _count("strategy_generations", "created_at>=?", (week_ago,)),
        "properties": _count("properties"),
        "messages": _count("contact_messages"),
        "cases": _count("case_submissions"),
    }
    recent = get_db().execute(
        "SELECT e.*,u.email FROM audit_events e LEFT JOIN users u ON u.id=e.user_id "
        "ORDER BY e.created_at DESC,e.id DESC LIMIT 15"
    ).fetchall()
    return render_template("admin/dashboard.html", metrics=metrics, events=recent, active_admin="dashboard")


@blueprint.get("/users")
@admin_required
def users_page():
    return render_template("admin/users.html", users=users.list_users(), active_admin="users")


@blueprint.get("/activity")
@admin_required
def activity():
    filter_name = str(request.args.get("type") or "").strip()
    params = []
    where = ""
    if filter_name in audit.ALLOWED_EVENT_TYPES:
        where = "WHERE e.event_type=?"
        params.append(filter_name)
    rows = get_db().execute(
        "SELECT e.*,u.email FROM audit_events e LEFT JOIN users u ON u.id=e.user_id "
        + where
        + " ORDER BY e.created_at DESC,e.id DESC LIMIT 300",
        tuple(params),
    ).fetchall()
    return render_template(
        "admin/activity.html",
        events=rows,
        current_filter=filter_name,
        available_events=sorted(audit.ALLOWED_EVENT_TYPES),
        active_admin="activity",
    )


@blueprint.get("/strategies")
@admin_required
def strategies_page():
    return render_template(
        "admin/strategies.html", generations=strategies.list_recent(), active_admin="strategies"
    )


@blueprint.get("/messages")
@admin_required
def messages():
    return render_template(
        "admin/messages.html", messages=submissions.list_messages(), active_admin="messages"
    )


@blueprint.get("/cases")
@admin_required
def cases():
    return render_template("admin/cases.html", cases=submissions.list_cases(), active_admin="cases")


@blueprint.get("/messages.csv")
@admin_required
def messages_csv():
    rows = submissions.list_messages(limit=5000)
    fields = ["id", "category", "subject", "message", "email", "wechat", "created_at"]
    return _csv_response(rows, fields, "expatus-contact-messages.csv")


@blueprint.get("/cases.csv")
@admin_required
def cases_csv():
    rows = submissions.list_cases(limit=5000)
    fields = [
        "id", "city", "contract_date", "rental_ended", "moveout_date", "base_rent", "deposit",
        "issues", "checkin_report", "deduction_spec", "description", "email", "wechat",
        "contact_ok", "created_at",
    ]
    return _csv_response(rows, fields, "expatus-case-submissions.csv")


def _csv_response(rows, fields, file_name):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        item = dict(row)
        if isinstance(item.get("issues"), list):
            item["issues"] = "、".join(item["issues"])
        sanitized = {}
        for field in fields:
            value = item.get(field, "")
            # Prevent spreadsheet formula injection in downloaded submissions.
            if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                value = "'" + value
            sanitized[field] = value
        writer.writerow(sanitized)
    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
