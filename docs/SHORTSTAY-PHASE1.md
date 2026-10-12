# Shortstay Phase 1 — read-only integration

This feature adds a public Jinja2 page at `/shortstay` to the existing Expatus Flask app and a read-only API at `/api/shortstay/listings?market=leiden&mode=30d`. It does **not** start a scraper, use Groq, create database tables, or change users / admin endpoints.

## Storage setup (later phase)

No environment variable is required to show the informative empty state.
To query the existing local Radar V2 database, set:

```env
SHORTSTAY_DB_PATH=/absolute/path/to/nl_shortstay.sqlite3
```

To use a **separate** dedicated Turso database (not Expatus production user-data DB), configure the read-only credential:

```env
SHORTSTAY_TURSO_DATABASE_URL=turso://example-shortstay
SHORTSTAY_TURSO_AUTH_TOKEN=<readonly-token>
```

Only the already-published fields of the Radar V2 `listings` table are read. Today's query means *first discovered today* (Europe/Amsterdam); 30-day query uses original source posting time, falling back to discovery. The URL, city, lease length and listing age are checked per market. The adapter reproduces V2 city ordering and intentionally doesn't depend on a global READY/REJECTED flag. Photos are placeholders until approved persistent media hosting is configured.

## Local verification

```bash
python tools/build_css.py
python -m unittest discover -s tests -v
python app.py
```

Verify `/shortstay`, `/api/shortstay/listings?market=leiden&mode=30d`, existing homepage, site navbar and admin login. The new page is `noindex` until real data is available. It is intentionally excluded from the sitemap at this stage.

## Safeguards

- New paths are isolated: `expatus/controllers/shortstay.py`, `expatus/repositories/shortstay.py`, `templates/pages/shortstay.html`, `static/css/src/pages/shortstay.css`, `static/css/dist/shortstay.css`, `static/js/shortstay.js`.
- Modified only Flask blueprint registration and both desktop/mobile navigation sections.
- Does not change `wsgi.py`, `vercel.json`, auth, the existing Turso database, or deployed environment variables.
- PR Preview must not share production credentials. Verify pre-existing site workflows before merging. Image storage, migration, admin-only copy/scan, and GitHub Actions scheduled collection are subsequent phases.
