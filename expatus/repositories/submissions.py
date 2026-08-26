"""Queries for contact messages and rental dispute submissions."""

from __future__ import annotations

import json

from expatus.database import get_db
from expatus.services.clock import utcnow


def create_message(user_id, item: dict) -> None:
    get_db().execute(
        "INSERT INTO contact_messages(user_id,category,subject,message,email,wechat,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (
            user_id,
            item["category"],
            item["subject"] or None,
            item["message"],
            item["email"] or None,
            item["wechat"] or None,
            utcnow().isoformat(),
        ),
    )
    get_db().commit()


def create_case(user_id, item: dict) -> None:
    get_db().execute(
        "INSERT INTO case_submissions(user_id,city,contract_date,rental_ended,moveout_date,"
        "base_rent,deposit,issues_json,checkin_report,deduction_spec,description,email,wechat,"
        "contact_ok,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            user_id,
            item["city"],
            item["contract_date"],
            item["rental_ended"],
            item["moveout_date"],
            item["base_rent"],
            item["deposit"],
            json.dumps(item["issues"], ensure_ascii=False),
            item["checkin_report"],
            item["deduction_spec"],
            item["description"],
            item["email"] or None,
            item["wechat"] or None,
            1 if item["contact_ok"] else 0,
            utcnow().isoformat(),
        ),
    )
    get_db().commit()


def list_messages(limit: int = 200):
    return get_db().execute(
        "SELECT * FROM contact_messages ORDER BY created_at DESC,id DESC LIMIT ?", (limit,)
    ).fetchall()


def list_cases(limit: int = 200):
    rows = get_db().execute(
        "SELECT * FROM case_submissions ORDER BY created_at DESC,id DESC LIMIT ?", (limit,)
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        try:
            item["issues"] = json.loads(item.get("issues_json") or "[]")
        except (ValueError, TypeError):
            item["issues"] = []
        result.append(item)
    return result
