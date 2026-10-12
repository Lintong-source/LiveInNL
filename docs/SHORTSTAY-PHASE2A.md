# Shortstay Phase 2A: publish local data safely

This is a **data-import tool**. It does not change Expatus users, properties,
account logins, production Vercel configuration, or run any housing scrapers.
The web UI stays read-only.

## Prerequisites (performed by a human, not committed to Git)

1. In Turso, create a **new, separate** database for Shortstay. Never reuse
   the existing Expatus user-data database. Create a dedicated write token.
2. In Vercel, optionally create a **public** Blob store for housing thumbnails.
   Record its `BLOB_READ_WRITE_TOKEN`; check provider and content permissions.
3. Configure Vercel Preview environment with:
   `SHORTSTAY_TURSO_DATABASE_URL` and `SHORTSTAY_TURSO_AUTH_TOKEN`
   from the **separate Shortstay database** (ideally a read-only token).
   Do not put secrets in Git or paste them into chat.
4. Wait for an approved Preview build. Phase 2A does not write production data.

## Run the publisher ON YOUR WSL COMPUTER

Clone/download the updated code or download this file from GitHub's raw view.
Use the actual V2 SQLite path:

```bash
python tools/shortstay_publish.py --db /mnt/d/myProjects/shortstay/data/nl_shortstay.sqlite3
```

This command does **NOT** connect to Turso or upload images.

For an approved one-time import, set the three environment variables locally:
`SHORTSTAY_TURSO_DATABASE_URL`, `SHORTSTAY_TURSO_AUTH_TOKEN`,
`SHORTSTAY_DATABASE_CONFIRMED=yes`, then run

```bash
pip install libsql turso_serverless
python tools/shortstay_publish.py --db /mnt/d/myProjects/shortstay/data/nl_shortstay.sqlite3 --apply
```

If a public Blob store is configured and uploading existing pictures is approved:

```bash
pip install vercel
python tools/shortstay_publish.py --db /mnt/d/myProjects/shortstay/data/nl_shortstay.sqlite3 --apply --with-images
```

Do not run on your only data copy without a SQLite backup. The script opens
local SQLite in read-only mode, but a backup is still good practice.

## Expected website behavior

- `/shortstay` uses the independent Turso data, does not use the Expatus
  `properties` table.
- The public API only exposes validated public fields, and image URLs only from
  public Vercel Blob hosts.
- Re-running publication uses URL upsert and never changes first discovery time.
- Listings older than 30 days remain in Turso for dedup but are not displayed;
  older images are not uploaded by this tool.
- **Deferred:** scheduled crawler from GitHub Actions, remote dedup synchronization,
  old cloud-photo deletion and administrator manual scan. Those need real storage
  credentials and integration testing before activation.

## Test

```bash
python -m unittest tests.test_shortstay_publish -v
python -m unittest discover -s tests -v
```

Never enable a public `POST /api/admin/scan` based on IP filtering in Vercel.
Use Expatus authenticated administrator session and CSRF protection.
