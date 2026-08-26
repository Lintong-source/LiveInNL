"""Persist generated strategy summaries without collecting identity documents."""

from __future__ import annotations

import json

from expatus.database import get_db
from expatus.services.clock import utcnow


def count_today(user_id: int) -> int:
    now = utcnow()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    return get_db().execute(
        "SELECT COUNT(*) AS total FROM strategy_generations WHERE user_id=? AND created_at>=?",
        (user_id, start),
    ).fetchone()["total"]


def create(user_id: int, profile: dict, summary: str, result: dict, engine_version: str) -> int:
    cursor = get_db().execute(
        "INSERT INTO strategy_generations(user_id,identity_type,city,move_date,home_type,budget,"
        "income_type,student_registration,university_housing,area_flexibility,result_summary,"
        "engine_version,result_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            user_id,
            profile["identity"],
            profile["city"],
            profile["moveDate"],
            profile["homeType"],
            profile["budget"],
            profile["income"],
            profile["studentReg"],
            profile["universityHousing"],
            profile["areaFlex"],
            summary[:240],
            engine_version,
            json.dumps(result, ensure_ascii=False, separators=(",", ":")),
            utcnow().isoformat(),
        ),
    )
    get_db().commit()
    return cursor.lastrowid


def latest_for_user(user_id: int):
    return get_db().execute(
        "SELECT * FROM strategy_generations WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 1",
        (user_id,),
    ).fetchone()


def profile_from_row(row) -> dict:
    return {
        "identity": row["identity_type"],
        "city": row["city"],
        "moveDate": row["move_date"],
        "homeType": row["home_type"],
        "budget": row["budget"],
        "income": row["income_type"],
        "studentReg": row["student_registration"],
        "universityHousing": row["university_housing"],
        "areaFlex": row["area_flexibility"],
    }


def list_recent(limit: int = 200):
    return get_db().execute(
        "SELECT s.*,u.email FROM strategy_generations s JOIN users u ON u.id=s.user_id "
        "ORDER BY s.created_at DESC,s.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
