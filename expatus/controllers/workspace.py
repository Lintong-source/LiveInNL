"""Authenticated personal-workspace APIs for listings, favorites and strategies."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, Response, abort, current_app, g, jsonify, redirect, request, session

from expatus.constants import END_REASONS, PLATFORM_BY_NAME, STATUSES
from expatus.database import get_db
from expatus.repositories import favorites, properties, strategies, users
from expatus.services import account_data, audit, progress_summary, strategy_engine
from expatus.services.security import api_login_required
from expatus.services.validation import parse_money, safe_next, safe_text, valid_http_url


blueprint = Blueprint("workspace", __name__)


def _property_or_404(property_id: int):
    item = properties.owned(property_id, g.user["id"])
    if item is None:
        abort(404)
    return item


def _property_payload(payload: dict) -> dict:
    name = safe_text(payload.get("name"), 180)
    source = safe_text(payload.get("source"), 120)
    url = safe_text(payload.get("url"), 2048)
    if not name:
        raise ValueError("请填写房源名称或地址。")
    if not valid_http_url(url):
        raise ValueError("房源链接需要以 http:// 或 https:// 开头。")
    return {"name": name, "source": source, "url": url, "rent": parse_money(payload.get("rent"))}


@blueprint.post("/api/favorites/toggle")
@api_login_required
def favorite_toggle():
    payload = request.get_json(silent=True) or {}
    platform = str(payload.get("platform") or "").strip()
    if platform not in PLATFORM_BY_NAME:
        return jsonify(ok=False, error="未找到这个平台。"), 400
    selected = favorites.toggle(g.user["id"], platform)
    audit.record("favorite_updated", details={"selected": selected})
    return jsonify(ok=True, favorite=selected)


@blueprint.post("/api/properties")
@api_login_required
def property_add():
    try:
        item = _property_payload(request.get_json(silent=True) or {})
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 400
    row = properties.create(g.user["id"], item)
    audit.record("property_created", details={"property_id": row["id"]})
    return jsonify(ok=True, property=properties.serialize(row))


@blueprint.get("/api/properties/summary")
@api_login_required
def property_summary():
    """Re-read the signed-in user's actual records without using browser cache."""
    return jsonify(ok=True, summary=progress_summary.for_user(g.user["id"]))


@blueprint.patch("/api/properties/<int:property_id>")
@api_login_required
def property_edit(property_id: int):
    _property_or_404(property_id)
    try:
        item = _property_payload(request.get_json(silent=True) or {})
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 400
    properties.update(property_id, item)
    audit.record("property_updated", details={"property_id": property_id, "action": "edit"})
    return jsonify(ok=True)


@blueprint.patch("/api/properties/<int:property_id>/status")
@api_login_required
def property_status(property_id: int):
    _property_or_404(property_id)
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in STATUSES:
        return jsonify(ok=False, error="无效状态。"), 400
    properties.update_status(property_id, status)
    audit.record(
        "property_updated", details={"property_id": property_id, "action": "status", "status": status}
    )
    return jsonify(ok=True)


@blueprint.post("/api/properties/<int:property_id>/end")
@api_login_required
def property_end(property_id: int):
    _property_or_404(property_id)
    reason = str((request.get_json(silent=True) or {}).get("reason") or "其他")
    properties.end(property_id, reason if reason in END_REASONS else "其他")
    audit.record("property_updated", details={"property_id": property_id, "action": "end"})
    return jsonify(ok=True)


@blueprint.post("/api/properties/<int:property_id>/restore")
@api_login_required
def property_restore(property_id: int):
    _property_or_404(property_id)
    properties.restore(property_id)
    audit.record("property_updated", details={"property_id": property_id, "action": "restore"})
    return jsonify(ok=True)


@blueprint.delete("/api/properties/<int:property_id>")
@api_login_required
def property_delete(property_id: int):
    _property_or_404(property_id)
    properties.delete(property_id)
    audit.record("property_deleted", details={"property_id": property_id})
    return jsonify(ok=True)


STRATEGY_CHOICES = {
    "identity": {"master", "bachelor", "phd", "worker", "family"},
    "city": {"Leiden", "Den Haag", "Rotterdam", "Amsterdam", "Utrecht"},
    "homeType": {"room", "studio", "apartment"},
    "income": {"none", "salary", "stipend"},
    "studentReg": {"unknown", "registered", "na"},
    "universityHousing": {"unknown", "waiting", "no"},
    "areaFlex": {"yes", "maybe"},
}


@blueprint.post("/api/strategies/generate")
@api_login_required
def strategy_generate():
    payload = request.get_json(silent=True) or {}
    for key, options in STRATEGY_CHOICES.items():
        if payload.get(key) not in options:
            return jsonify(ok=False, error=f"找房资料中 {key} 的值不正确。"), 400
    try:
        move_date = date.fromisoformat(str(payload.get("moveDate") or ""))
        budget = int(payload.get("budget"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="入住日期或预算格式不正确。"), 400
    if budget < 300 or budget > 100_000:
        return jsonify(ok=False, error="预算不在合理范围内。"), 400
    used = strategies.count_today(g.user["id"])
    if used >= 3:
        return jsonify(ok=False, error="今天的 3 次策略生成已用完。", used_today=used), 429
    profile = {key: payload[key] for key in STRATEGY_CHOICES}
    profile["moveDate"] = move_date.isoformat()
    profile["budget"] = budget
    progress = progress_summary.for_user(g.user["id"])
    result = strategy_engine.generate(profile, progress)
    summary = f"{profile['city']} · {profile['homeType']} · €{budget}"
    generation_id = strategies.create(
        g.user["id"], profile, summary, result, strategy_engine.ENGINE_VERSION
    )
    audit.record(
        "strategy_generated",
        details={"generation_id": generation_id, "city": profile["city"], "engine_version": strategy_engine.ENGINE_VERSION},
    )
    return jsonify(
        ok=True,
        generation_id=generation_id,
        used_today=used + 1,
        daily_limit=3,
        strategy=result,
    )


@blueprint.get("/api/strategies/current")
@api_login_required
def strategy_current():
    """Recalculate the latest profile against the current account progress."""
    latest = strategies.latest_for_user(g.user["id"])
    if latest is None:
        return jsonify(ok=False, error="请先生成一份找房策略。"), 404
    profile = strategies.profile_from_row(latest)
    progress = progress_summary.for_user(g.user["id"])
    return jsonify(ok=True, strategy=strategy_engine.generate(profile, progress))


@blueprint.get("/api/account/export")
@api_login_required
def account_export():
    result = account_data.collect(g.user)
    audit.record("account_exported")
    if request.args.get("format") == "json":
        return jsonify(result)
    response = Response(account_data.build_archive(result), mimetype="application/zip")
    response.headers["Content-Disposition"] = 'attachment; filename="expatus-personal-data.zip"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


@blueprint.post("/api/account/privacy/acknowledge")
@api_login_required
def privacy_acknowledge():
    settings = current_app.config["EXPATUS_SETTINGS"]
    users.acknowledge_privacy(g.user["id"], settings.privacy_policy_version)
    audit.record("privacy_acknowledged", details={"version": settings.privacy_policy_version})
    return redirect(safe_next(request.form.get("next") or "/workspace/strategy"))


@blueprint.delete("/api/account")
@api_login_required
def account_delete():
    user_id = g.user["id"]
    audit.record("account_deleted", user_id=user_id)
    get_db().execute("DELETE FROM users WHERE id=?", (user_id,))
    get_db().commit()
    session.clear()
    return jsonify(ok=True, message="账户及相关找房记录已经删除。")
