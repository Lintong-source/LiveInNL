"""Persistence operations for account-owned rental listings."""

from __future__ import annotations

from expatus.database import get_db
from expatus.services.clock import utcnow


def serialize(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "source": row["source"] or "",
        "rent": row["rent"],
        "url": row["url"] or "",
        "status": row["status"],
        "is_ended": bool(row["is_ended"]),
        "reason": row["end_reason"] or "",
    }


def list_for_user(user_id: int):
    return get_db().execute(
        "SELECT * FROM properties WHERE user_id=? "
        "ORDER BY is_ended ASC,updated_at DESC,id DESC",
        (user_id,),
    ).fetchall()


def owned(property_id: int, user_id: int):
    return get_db().execute(
        "SELECT * FROM properties WHERE id=? AND user_id=?", (property_id, user_id)
    ).fetchone()


def create(user_id: int, data: dict):
    now = utcnow().isoformat()
    cursor = get_db().execute(
        "INSERT INTO properties(user_id,name,source,rent,url,status,is_ended,created_at,updated_at) "
        "VALUES(?,?,?,?,?,'待处理',0,?,?)",
        (user_id, data["name"], data["source"], data["rent"], data["url"] or None, now, now),
    )
    get_db().commit()
    return owned(cursor.lastrowid, user_id)


def update(property_id: int, data: dict) -> None:
    get_db().execute(
        "UPDATE properties SET name=?,source=?,rent=?,url=?,updated_at=? WHERE id=?",
        (
            data["name"],
            data["source"],
            data["rent"],
            data["url"] or None,
            utcnow().isoformat(),
            property_id,
        ),
    )
    get_db().commit()


def update_status(property_id: int, status: str) -> None:
    get_db().execute(
        "UPDATE properties SET status=?,is_ended=0,end_reason=NULL,ended_at=NULL,updated_at=? WHERE id=?",
        (status, utcnow().isoformat(), property_id),
    )
    get_db().commit()


def end(property_id: int, reason: str) -> None:
    now = utcnow().isoformat()
    get_db().execute(
        "UPDATE properties SET is_ended=1,end_reason=?,ended_at=?,updated_at=? WHERE id=?",
        (reason, now, now, property_id),
    )
    get_db().commit()


def restore(property_id: int) -> None:
    get_db().execute(
        "UPDATE properties SET status='待处理',is_ended=0,end_reason=NULL,ended_at=NULL,updated_at=? "
        "WHERE id=?",
        (utcnow().isoformat(), property_id),
    )
    get_db().commit()


def delete(property_id: int) -> None:
    get_db().execute("DELETE FROM properties WHERE id=?", (property_id,))
    get_db().commit()
