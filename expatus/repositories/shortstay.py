"""Isolated read-only adapter for Shortstay Radar V2 database.

It never reads or writes Expatus's accounts/properties database.
No table creation/migration in public HTTP requests.
"""
from __future__ import annotations

import calendar
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Amsterdam")
MARKETS = {
    "leiden": "Leiden",
    "amsterdam": "Amsterdam",
    "denhaag": "Den Haag",
    "rotterdam": "Rotterdam",
    "utrecht": "Utrecht",
}
# Same ordering as Radar V2's city_order.yaml. Geographical eligibility
# additionally covers its core/review whitelist.
CITY_ORDER = {
    "leiden": ["Leiden","Oegstgeest","Leiderdorp","Voorschoten","Warmond","Rijnsburg","Katwijk","Wassenaar","Noordwijk","Alphen aan den Rijn","Zoetermeer","Den Haag","Delft","Gouda","Haarlem","Hoofddorp","Amsterdam","Rotterdam","Utrecht"],
    "denhaag": ["Den Haag","Voorburg","Rijswijk","Leidschendam","Wassenaar","Delft","Zoetermeer","Leiden","Rotterdam","Schiedam","Gouda","Alphen aan den Rijn","Amsterdam","Utrecht"],
    "rotterdam": ["Rotterdam","Schiedam","Vlaardingen","Capelle aan den IJssel","Barendrecht","Ridderkerk","Delft","Den Haag","Zoetermeer","Dordrecht","Gouda","Leiden","Utrecht","Amsterdam"],
    "amsterdam": ["Amsterdam","Amstelveen","Diemen","Zaandam","Weesp","Haarlem","Hoofddorp","Almere","Hilversum","Utrecht","Leiden","Den Haag","Rotterdam"],
    "utrecht": ["Utrecht","Nieuwegein","Houten","Zeist","De Bilt","Maarssen","Woerden","Amersfoort","Hilversum","Amsterdam","Gouda","Rotterdam","Den Haag","Leiden"],
}
CITY_EXTRA = {
    "leiden": ["Schiedam","Amstelveen","Woerden","Dordrecht","Zaandam"],
    "denhaag": ["Haarlem","Hoofddorp","Katwijk","Dordrecht"],
    "rotterdam": ["Breda","Alphen aan den Rijn","Haarlem"],
    "amsterdam": ["Duivendrecht","Gouda","Delft","Purmerend","Amersfoort","Alkmaar"],
    "utrecht": ["Delft","Haarlem","Almere","Breda","Arnhem"],
}
ALIASES = {"the hague":"den haag","'s-gravenhage":"den haag","s-gravenhage":"den haag","denhaag":"den haag","den bosch":"'s-hertogenbosch"}

def city_key(value):
    name = " ".join(str(value or "").strip().lower().split())
    return ALIASES.get(name, name)

def utc_datetime(value):
    if not value:
        return None
    try:
        v = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None

def iso_date(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except (ValueError, TypeError):
        return None

def plus_months(day, n):
    index = day.month-1+n
    year, month = day.year+index//12, index%12+1
    return date(year, month, min(day.day, calendar.monthrange(year,month)[1]))

def qualifies_stay(canonical, today):
    stay = canonical.get("stay") or {}
    if not isinstance(stay, dict):
        return False
    begin, end = iso_date(stay.get("start_date")), iso_date(stay.get("end_date"))
    if end and end < today:
        return False
    if begin and end:
        if end < begin:
            return False
        if end <= plus_months(begin, 3):
            return True
        # V2 permits a longer available window ONLY when a shorter
        # permissible minimum duration is explicitly present.
    try:
        if stay.get("min_stay_months") is not None:
            return 0 <= float(stay["min_stay_months"]) <= 3
        if stay.get("min_stay_days") is not None:
            return 0 <= float(stay["min_stay_days"]) <= 92
        if begin and end:
            return False
        if stay.get("max_stay_months") is not None:
            return 0 <= float(stay["max_stay_months"]) <= 3
        if stay.get("max_stay_days") is not None:
            return 0 <= float(stay["max_stay_days"]) <= 92
    except (ValueError, TypeError):
        return False
    return stay.get("mode") == "temporary_unspecified"

def public_url(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    return value if parsed.scheme in {"https","http"} and parsed.hostname else None

@contextmanager
def read_connection():
    url = os.getenv("SHORTSTAY_TURSO_DATABASE_URL", "").strip()
    token = os.getenv("SHORTSTAY_TURSO_AUTH_TOKEN", "").strip()
    path = os.getenv("SHORTSTAY_DB_PATH", "").strip()
    if bool(url) != bool(token):
        raise RuntimeError("Shortstay remote DB credentials incomplete")
    if url:
        if url.startswith("turso://"):
            import turso_serverless
            conn = turso_serverless.connect(url, auth_token=token)
        else:
            import libsql
            conn = libsql.connect(database=url, auth_token=token)
    elif path:
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            raise RuntimeError("Shortstay database does not exist")
        conn = sqlite3.connect(f"file:{p.as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    else:
        yield None
        return
    try:
        yield conn
    finally:
        conn.close()

def _rows(conn):
    # Status is intentionally NOT a filter: Radar V2 recomputes eligibility
    # for each market, because one global status can reflect another market.
    cur = conn.execute(
        "SELECT id,listing_uid,url,source,source_posted_at,first_seen_at,"
        "status,canonical_json FROM listings "
        "WHERE canonical_json IS NOT NULL ORDER BY id DESC LIMIT 15000"
    )
    columns = [col[0] for col in cur.description]
    return [dict(zip(columns, tuple(row))) for row in cur.fetchall()]

def query_listings(market="leiden", mode="today", *, connection=None, now=None, limit=300):
    if market not in MARKETS or mode not in {"today","30d"}:
        raise ValueError("Unknown market/mode")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    local_today = now.astimezone(TZ).date()
    allowed = {city_key(x) for x in CITY_ORDER[market] + CITY_EXTRA[market]}
    priority = {city_key(x): i for i,x in enumerate(CITY_ORDER[market])}
    if connection is None:
        with read_connection() as conn:
            if conn is None:
                return {"configured":False,"count":0,"items":[]}
            rows = _rows(conn)
    else:
        rows = _rows(connection)
    items=[]
    for row in rows:
        try:
            c = json.loads(row["canonical_json"] or "{}")
            if not isinstance(c,dict):
                continue
            place = str(c.get("city") or "").strip()
            normalized = city_key(place)
            if not normalized or normalized not in allowed or not qualifies_stay(c,local_today):
                continue
            posted = utc_datetime(row["source_posted_at"]) or utc_datetime(row["first_seen_at"])
            discovered = utc_datetime(row["first_seen_at"])
            if not posted or not discovered:
                continue
            age = (now-posted).total_seconds()/86400
            if age < -1 or age > 30:
                continue
            if mode=="today" and discovered.astimezone(TZ).date()!=local_today:
                continue
            url = public_url(row["url"])
            if not url:
                continue
            days = max(0,(local_today-posted.astimezone(TZ).date()).days)
            band = "0–3天" if days<=3 else "4–7天" if days<=7 else "8–14天" if days<=14 else "15–30天"
            stay = c.get("stay") or {}
            if not isinstance(stay,dict):
                stay={}
            rent = c.get("rent_eur")
            if isinstance(rent,bool) or not isinstance(rent,(float,int)) or not 0 <= rent <= 100000:
                rent = None
            items.append({
                "uid":str(row["listing_uid"] or row["id"]),
                "city":place,
                "city_group":normalized,
                "address":str(c.get("address") or "")[:180],
                "title":str(c.get("title_cn") or "临时房源")[:140],
                "summary":str(c.get("summary_cn") or "")[:1200],
                "price_eur":rent,
                "room_type":str(c.get("room_type") or "unknown")[:30],
                "start_date":str(stay.get("start_date") or "")[:10],
                "end_date":str(stay.get("end_date") or "")[:10],
                "posted_at":posted.isoformat(),
                "freshness":"今天" if days==0 else f"{days}天前",
                "age_band":band,
                "original_url":url,
                # Radar V2's local_image is a WSL path, not a public URL.
                # Images require separately approved persistent hosting.
                "image_url":None,
                "_sort":(priority.get(normalized,len(priority)+1),-posted.timestamp(),row["id"]),
            })
        except (ValueError,TypeError,KeyError):
            continue
    items.sort(key=lambda item:item["_sort"])
    items=items[:max(1,min(limit,300))]
    for item in items: item.pop("_sort",None)
    return {"configured":True,"count":len(items),"items":items}
