"""Spam-resistant public contact and rental-dispute form endpoints."""

from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from expatus.repositories import submissions
from expatus.services import audit
from expatus.services.security import check_rate_limit
from expatus.services.validation import (
    enforce_reasonable_links,
    ensure_meaningful_message,
    ensure_meaningful_subject,
    ensure_reasonable_contact,
    normalize_email,
    parse_money,
    safe_text,
    valid_email,
)


blueprint = Blueprint("submissions", __name__)


def _spam_gate(payload: dict, bucket: str):
    # Bots commonly populate the visually hidden website field.
    if payload.get("website"):
        return jsonify(ok=True, message="已收到。")
    if not check_rate_limit(bucket, maximum=5, seconds=3600):
        return jsonify(ok=False, error="提交次数较多，请稍后再试。"), 429
    return None


@blueprint.post("/api/contact")
def contact_submit():
    payload = request.get_json(silent=True) or {}
    blocked = _spam_gate(payload, "contact_form")
    if blocked is not None:
        return blocked
    try:
        category = safe_text(payload.get("category") or "其他", 40)
        if category not in {"网站建议", "找房资源补充", "租房问题", "合作", "其他"}:
            category = "其他"
        message = safe_text(payload.get("message"), 4000, multiline=True)
        ensure_meaningful_message(message)
        enforce_reasonable_links(message)
        email = normalize_email(payload.get("email"))
        if email and not valid_email(email):
            raise ValueError("邮箱格式不正确。")
        subject = safe_text(payload.get("subject"), 120)
        wechat = safe_text(payload.get("wechat"), 120)
        ensure_meaningful_subject(subject)
        ensure_reasonable_contact(email, wechat)
        item = {
            "category": category,
            "subject": subject,
            "message": message,
            "email": email,
            "wechat": wechat,
        }
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 400
    submissions.create_message(g.user["id"] if g.user else None, item)
    audit.record("message_submitted", details={"category": category})
    return jsonify(ok=True)


@blueprint.post("/api/cases")
def case_submit():
    payload = request.get_json(silent=True) or {}
    blocked = _spam_gate(payload, "case_form")
    if blocked is not None:
        return blocked
    try:
        description = safe_text(payload.get("description"), 5000, multiline=True)
        ensure_meaningful_message(description, minimum=10)
        enforce_reasonable_links(description)
        email = normalize_email(payload.get("email"))
        if email and not valid_email(email):
            raise ValueError("邮箱格式不正确。")
        wechat = safe_text(payload.get("wechat"), 120)
        ensure_reasonable_contact(email, wechat)
        raw_issues = payload.get("issues") or []
        if not isinstance(raw_issues, list):
            raw_issues = []
        item = {
            "city": safe_text(payload.get("city"), 120),
            "contract_date": safe_text(payload.get("contract_date"), 20),
            "rental_ended": safe_text(payload.get("rental_ended"), 30),
            "moveout_date": safe_text(payload.get("moveout_date"), 20),
            "base_rent": parse_money(payload.get("base_rent")),
            "deposit": parse_money(payload.get("deposit")),
            "issues": [safe_text(value, 60) for value in raw_issues[:12]],
            "checkin_report": safe_text(payload.get("checkin_report"), 30),
            "deduction_spec": safe_text(payload.get("deduction_spec"), 30),
            "description": description,
            "email": email,
            "wechat": wechat,
            "contact_ok": bool(payload.get("contact_ok")),
        }
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 400
    submissions.create_case(g.user["id"] if g.user else None, item)
    audit.record("case_submitted", details={"contact_ok": item["contact_ok"]})
    return jsonify(ok=True)
