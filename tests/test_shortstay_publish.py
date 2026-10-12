"""Offline tests for safe, repeatable Shortstay data publication."""
import importlib.util, os, sqlite3, tempfile, unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
PATH=Path(__file__).resolve().parents[1]/"tools"/"shortstay_publish.py"
spec=importlib.util.spec_from_file_location("shortstay_publish_test",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class PublishTests(unittest.TestCase):
    def test_schema(self):
        c=sqlite3.connect(":memory:")
        for sql in mod.make_schema(): c.execute(sql)
        names=[r[1] for r in c.execute("PRAGMA table_info(listings)")]
        self.assertIn("public_image_url",names)

    def test_idempotent_and_original_first_seen(self):
        db=sqlite3.connect(":memory:")
        class Adapter:
            def execute(self,*args):return db.execute(*args)
            def commit(self):db.commit()
            def close(self):pass
        row={"url":"https://example.com/room","source":"kamernet",
             "first_seen_at":"2026-10-01T00:00:00+00:00",
             "last_seen_at":"2026-10-02T00:00:00+00:00",
             "canonical_json":'{"city":"Leiden"}'}
        with patch.dict(os.environ,{"SHORTSTAY_TURSO_DATABASE_URL":"test",
                                    "SHORTSTAY_TURSO_AUTH_TOKEN":"test",
                                    "SHORTSTAY_DATABASE_CONFIRMED":"yes"}):
            mod.publish(Path("/tmp/data/x.sqlite3"),[row],connect=lambda *x:Adapter())
            mod.publish(Path("/tmp/data/x.sqlite3"),[{**row,"first_seen_at":"2026-10-10T00:00:00+00:00",
                "canonical_json":'{"city":"Delft"}'}],connect=lambda *x:Adapter())
        self.assertEqual(db.execute("SELECT COUNT(*) FROM listings").fetchone()[0],1)
        value=db.execute("SELECT first_seen_at,canonical_json FROM listings").fetchone()
        self.assertEqual(value[0],row["first_seen_at"])
        self.assertIn("Delft",value[1])

    def test_requires_confirmation(self):
        with patch.dict(os.environ,{"SHORTSTAY_TURSO_DATABASE_URL":"test",
                                    "SHORTSTAY_TURSO_AUTH_TOKEN":"test",
                                    "SHORTSTAY_DATABASE_CONFIRMED":"no"}):
            with self.assertRaisesRegex(RuntimeError,"DEDICATED"):
                mod.publish(Path("/tmp/data/x.sqlite3"),[],connect=lambda *x:None)

    def test_sandbox_images(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"output"/"images").mkdir(parents=True)
            f=root/"output"/"images"/"a.png";f.write_bytes(b"test")
            row={"source_posted_at":datetime.now(timezone.utc).isoformat(),"local_image":str(f)}
            self.assertEqual(mod.local_photo(row,root),f)
            self.assertIsNone(mod.local_photo({**row,"local_image":"/etc/hosts"},root))
            self.assertIsNone(mod.local_photo({**row,
              "source_posted_at":(datetime.now(timezone.utc)-timedelta(days=31)).isoformat()},root))

    def test_transient_reconnect_and_per_row_commit(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"remote.sqlite3"
            attempts=[0]
            commits=[0]
            class Adapter:
                def __init__(self):
                    self.db=sqlite3.connect(path)
                def execute(self,sql,params=()):
                    if "INSERT INTO listings(" in sql and attempts[0]==0:
                        attempts[0]+=1
                        raise ValueError("Hrana: connection closed before message completed")
                    return self.db.execute(sql,params)
                def commit(self):
                    commits[0]+=1
                    self.db.commit()
                def close(self):
                    self.db.close()
            now="2026-10-11T10:00:00+00:00"
            rows=[{"url":f"https://example.org/{i}","source":"kamernet",
                   "first_seen_at":now,"last_seen_at":now,
                   "canonical_json":'{"city":"Leiden"}'} for i in range(3)]
            connections=[0]
            def connect(*_):
                connections[0]+=1
                return Adapter()
            with patch.dict(os.environ,{"SHORTSTAY_TURSO_DATABASE_URL":"test",
                                        "SHORTSTAY_TURSO_AUTH_TOKEN":"test",
                                        "SHORTSTAY_DATABASE_CONFIRMED":"yes"}):
                count,_=mod.publish(Path(folder)/"data"/"source.sqlite3",rows,
                                    connect=connect,sleep=lambda _:None)
            self.assertEqual(count,3)
            self.assertGreaterEqual(connections[0],2)
            self.assertGreaterEqual(commits[0],3)
            with sqlite3.connect(path) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM listings").fetchone()[0],3)

    def test_safe_url(self):
        self.assertIsNone(mod.public_url("javascript:alert(1)"))
        self.assertIsNone(mod.public_url("https://evil.example/"))
        self.assertTrue(mod.public_url("https://a.public.blob.vercel-storage.com/a.png"))

if __name__=="__main__":unittest.main()
