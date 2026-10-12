#!/usr/bin/env python3
"""Opt-in, one-way V2 SQLite -> dedicated Turso publication (DRY RUN by default).
Never points at Expatus user data or creates anything through an HTTP request.
"""
from __future__ import annotations
import argparse, hashlib, os, sqlite3, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

COL_TYPES = {
    "url":"TEXT UNIQUE NOT NULL", "source":"TEXT NOT NULL", "listing_uid":"TEXT",
    "search_hash":"TEXT", "detail_hash":"TEXT",
    "first_seen_at":"TEXT NOT NULL", "last_seen_at":"TEXT NOT NULL",
    "source_posted_at":"TEXT", "status":"TEXT", "reason":"TEXT",
    "geo_bucket":"TEXT", "duplicate_of":"INTEGER", "fingerprint":"TEXT",
    "image_url":"TEXT", "local_image":"TEXT", "raw_json":"TEXT",
    "canonical_json":"TEXT", "message_cn":"TEXT", "last_error":"TEXT",
    "image_cleaned_at":"TEXT", "expires_at":"TEXT",
    "image_attempted_at":"TEXT", "public_image_url":"TEXT"
}
COLS = tuple(COL_TYPES)

def make_schema():
    fields=",\n  ".join(f"{key} {kind}" for key,kind in COL_TYPES.items())
    return (
        f"CREATE TABLE IF NOT EXISTS listings (id INTEGER PRIMARY KEY AUTOINCREMENT,\n  {fields})",
        "CREATE INDEX IF NOT EXISTS idx_shortstay_posted ON listings(source_posted_at)",
        "CREATE INDEX IF NOT EXISTS idx_shortstay_seen ON listings(first_seen_at)"
    )

def dt(value):
    try:
        parsed=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except (ValueError,TypeError):
        return None

def stable_uid(row):
    return row.get("listing_uid") or hashlib.sha256(
        f'{row.get("source")}|{row["url"].split("?")[0].rstrip("/")}'.encode()
    ).hexdigest()[:20]

def load_local(path):
    source=Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Local Shortstay V2 database not found: {source}")
    c=sqlite3.connect(f"file:{source.as_posix()}?mode=ro",uri=True)
    c.row_factory=sqlite3.Row
    try:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='listings'").fetchone():
            raise ValueError("Invalid Shortstay V2 database: listings table missing")
        rows=[dict(r) for r in c.execute("SELECT * FROM listings ORDER BY id")]
        if rows and not {"url","source","first_seen_at","last_seen_at","canonical_json"}.issubset(rows[0]):
            raise ValueError("Unsupported Shortstay listings schema")
        return source, rows
    finally:
        c.close()

def public_url(value):
    if not isinstance(value,str): return None
    try:
        parsed=urlsplit(value)
        return value if parsed.scheme=="https" and parsed.hostname and parsed.hostname.endswith(".public.blob.vercel-storage.com") else None
    except ValueError:
        return None

def local_photo(row,root,now=None):
    time=dt(row.get("source_posted_at")) or dt(row.get("first_seen_at"))
    if time is None or time < (now or datetime.now(timezone.utc))-timedelta(days=30):
        return None
    raw=row.get("local_image")
    if not raw: return None
    path=Path(raw)
    if not path.is_absolute():path=root/path
    path=path.resolve()
    if (root/"output"/"images").resolve() not in path.parents or not path.is_file():
        return None
    if path.suffix.lower() not in {".png",".jpg",".jpeg",".webp"}:return None
    if not 0 < path.stat().st_size <= 3_000_000:return None
    return path

def remote_connect(url,token):
    if url.startswith("turso://"):
        import turso_serverless
        return turso_serverless.connect(url,auth_token=token)
    import libsql
    return libsql.connect(database=url,auth_token=token)

def upload_photo(path,uid,token):
    from vercel.blob import BlobClient
    raw=path.read_bytes()
    checksum=hashlib.sha256(raw).hexdigest()[:16]
    suffix=path.suffix.lower()
    result=BlobClient().put(
        f"shortstay/{uid}-{checksum}{suffix}",raw,access="public",
        add_random_suffix=False,content_type={
            ".png":"image/png",".jpg":"image/jpeg",
            ".jpeg":"image/jpeg",".webp":"image/webp"}[suffix],
        token=token
    )
    return public_url(result.url)

def _is_temporary_connection_error(error):
    """Only retry transport failures; auth, syntax, or schema errors must surface."""
    msg = str(error).lower()
    return any(part in msg for part in (
        "connection closed", "connection reset", "stream expired",
        "timed out", "timeout", "unexpected eof", "broken pipe"
    ))

def _close_quietly(connection):
    if connection is not None:
        try:
            connection.close()
        except Exception:
            pass

def publish(source, rows, *, connect=remote_connect, images=False,
            upload=upload_photo, max_retries=3, sleep=time.sleep):
    url=os.getenv("SHORTSTAY_TURSO_DATABASE_URL","").strip()
    token=os.getenv("SHORTSTAY_TURSO_AUTH_TOKEN","").strip()
    if not url or not token:
        raise RuntimeError("Dedicated Shortstay Turso URL and auth token required")
    if os.getenv("SHORTSTAY_DATABASE_CONFIRMED","").strip().lower()!="yes":
        raise RuntimeError("Set SHORTSTAY_DATABASE_CONFIRMED=yes for a verified DEDICATED Shortstay DB")
    blob_token=os.getenv("BLOB_READ_WRITE_TOKEN","").strip()
    if images and not blob_token:
        raise RuntimeError("--with-images requires a PUBLIC Vercel Blob store token")

    remote=None
    written=uploaded=0
    try:
        remote=connect(url,token)
        for statement in make_schema():
            remote.execute(statement)
            remote.commit()
        print("Cloud schema ready.",flush=True)
        for index,row in enumerate(rows,1):
            if not row.get("url") or not row.get("source"):
                print(f"Skipping invalid row {index}/{len(rows)}",flush=True)
                continue
            fields=",".join(COLS)
            placeholders=",".join("?" for _ in COLS)
            changes=",".join(f"{k}=excluded.{k}" for k in COLS
                             if k not in {"url","first_seen_at","listing_uid"})
            statement=(
                f"INSERT INTO listings({fields}) VALUES ({placeholders}) "
                f"ON CONFLICT(url) DO UPDATE SET {changes}"
            )
            for attempt in range(max_retries+1):
                try:
                    previous=remote.execute(
                        "SELECT public_image_url FROM listings WHERE url=?",(row["url"],)
                    ).fetchone()
                    image=public_url(previous[0]) if previous else None
                    photo=local_photo(row,source.parent.parent)
                    if images and photo and not image:
                        image=upload(photo,stable_uid(row),blob_token)
                        if not image:
                            raise ValueError("Unexpected image storage URL")
                        uploaded+=1
                    values={k:row.get(k) for k in COLS}
                    values["listing_uid"]=stable_uid(row)
                    values["local_image"]=None
                    values["public_image_url"]=image
                    remote.execute(statement,tuple(values[k] for k in COLS))
                    # Crucial: commit EACH row. Long-lived transactions over
                    # hundreds of HTTP round trips can expire in Hrana.
                    remote.commit()
                    written+=1
                    if index%10==0 or index==len(rows):
                        print(f"Committed {index}/{len(rows)} local rows "
                              f"({written} published)",flush=True)
                    break
                except Exception as exc:
                    # A failed Hrana request invalidates the existing stream.
                    _close_quietly(remote)
                    remote=None
                    if attempt>=max_retries or not _is_temporary_connection_error(exc):
                        raise RuntimeError(
                            f"Cloud write stopped at local row {index}/{len(rows)} "
                            f"(successfully committed {written} this run); "
                            f"data size: {len(str(row.get('raw_json') or '')) + len(str(row.get('canonical_json') or ''))} characters. "
                            f"Cause: {type(exc).__name__}: {exc}"
                        ) from exc
                    delay=min(2**attempt,4)
                    print(f"Transient Turso connection error at row {index}/{len(rows)}. "
                          f"Reconnecting after {delay}s (retry {attempt+1}/{max_retries}).",
                          flush=True)
                    sleep(delay)
                    remote=connect(url,token)
    finally:
        _close_quietly(remote)
    return written,uploaded

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db",required=True,help="Local nl_shortstay.sqlite3 file")
    parser.add_argument("--apply",action="store_true",help="Actually write to cloud")
    parser.add_argument("--with-images",action="store_true",help="Upload recent photos to Blob")
    args=parser.parse_args()
    source,rows=load_local(args.db)
    photo_count=sum(local_photo(row,source.parent.parent) is not None for row in rows)
    print(f"Local database: {source}\nListings: {len(rows)}\nRecent cached photos: {photo_count}")
    if not args.apply:
        print("DRY RUN ONLY. No cloud writes. Use --apply only after independent database setup.")
        return
    total,photos=publish(source,rows,images=args.with_images)
    print(f"Published: {total} records, {photos} images")

if __name__=="__main__":main()
