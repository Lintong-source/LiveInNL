"""Derive strategy feedback exclusively from one account's rental records."""

from __future__ import annotations

from collections import Counter

from expatus.constants import STATUSES
from expatus.repositories import properties


STATUS_RANK = {status: index for index, status in enumerate(STATUSES)}


def _channel(source: str) -> str:
    value = source.lower()
    if any(word in value for word in ("pararius", "funda", "huurwoningen")):
        return "commercial"
    if any(word in value for word in ("kamernet", "facebook", "微信", "社群", "朋友")):
        return "social"
    if any(word in value for word in ("room", "duwo", "ssh", "student", "学生")):
        return "passive"
    return "mixed"


def for_user(user_id: int) -> dict:
    """Return server-derived counters; ended listings cannot become active offers."""
    tracked = properties.list_for_user(user_id)
    contacted = [item for item in tracked if STATUS_RANK.get(item["status"], 0) >= 1]
    channels = Counter(_channel(item["source"] or "") for item in contacted)
    channels.pop("mixed", None)
    ordered_channels = channels.most_common()
    main_channel = (
        ordered_channels[0][0]
        if ordered_channels
        and (len(ordered_channels) == 1 or ordered_channels[0][1] > ordered_channels[1][1])
        else "mixed"
    )

    return {
        "applications": len(contacted),
        "replies": sum(
            STATUS_RANK.get(item["status"], 0) >= STATUS_RANK["已收到回复"]
            for item in tracked
        ),
        "viewings": sum(
            STATUS_RANK.get(item["status"], 0) >= STATUS_RANK["已预约看房"]
            for item in tracked
        ),
        "active": sum(
            not item["is_ended"]
            and 1 <= STATUS_RANK.get(item["status"], 0) < STATUS_RANK["已签约"]
            for item in tracked
        ),
        "confirmed": sum(
            not item["is_ended"] and item["status"] == "已签约" for item in tracked
        ),
        "mainChannel": main_channel,
        "tracked": len(tracked),
    }
