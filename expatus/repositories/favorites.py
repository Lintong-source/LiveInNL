"""Storage for a user's saved rental platforms."""

from expatus.database import get_db
from expatus.services.clock import utcnow


def names_for_user(user_id: int) -> list[str]:
    rows = get_db().execute(
        "SELECT platform FROM favorites WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    return [row["platform"] for row in rows]


def toggle(user_id: int, platform: str) -> bool:
    row = get_db().execute(
        "SELECT id FROM favorites WHERE user_id=? AND platform=?", (user_id, platform)
    ).fetchone()
    if row:
        get_db().execute("DELETE FROM favorites WHERE id=?", (row["id"],))
        result = False
    else:
        get_db().execute(
            "INSERT INTO favorites(user_id,platform,created_at) VALUES(?,?,?)",
            (user_id, platform, utcnow().isoformat()),
        )
        result = True
    get_db().commit()
    return result
