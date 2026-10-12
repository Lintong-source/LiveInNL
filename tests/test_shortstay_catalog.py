"""Read-only Shortstay API catalog adapter tests; no production credentials."""
import importlib.util
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/"expatus"/"repositories"/"shortstay.py"
spec=importlib.util.spec_from_file_location("shortstay_catalog_test",PATH)
catalog=importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)

class ShortstayCatalogTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.file=Path(self.temp.name)/"catalog.db"
        self.db=sqlite3.connect(self.file)
        self.db.execute("""CREATE TABLE listings(
            id INTEGER PRIMARY KEY,listing_uid TEXT,url TEXT,source TEXT,
            source_posted_at TEXT,first_seen_at TEXT,status TEXT,canonical_json TEXT)""")
        self.now=datetime.now(timezone.utc).replace(microsecond=0)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def put(self, city="Leiden", days=1, status="READY", stay=None, url=None, discovered_days=None):
        posted=self.now-timedelta(days=days)
        seen=self.now-timedelta(days=discovered_days if discovered_days is not None else days)
        data={"city":city,"address":"Stationsweg","title_cn":"短租房间","summary_cn":"测试用文字",
              "rent_eur":650,"room_type":"room",
              "stay":stay if stay is not None else {"mode":"fixed","start_date":"2027-01-01","end_date":"2027-03-01"}}
        self.db.execute("""INSERT INTO listings(url,source,source_posted_at,first_seen_at,status,canonical_json)
            VALUES(?,?,?,?,?,?)""",(url or "https://example.org/"+city.replace(" ","-")+str(days)+status,
            "kamernet",posted.isoformat(),seen.isoformat(),status,json.dumps(data,ensure_ascii=False)))
        self.db.commit()

    def test_no_connection_returns_empty_not_fake_records(self):
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(catalog.query_listings("leiden","today")["configured"])

    def test_city_priority_over_recency(self):
        self.put("Amsterdam",days=1)
        self.put("Leiden",days=4)
        out=catalog.query_listings("leiden","30d",connection=self.db,now=self.now)
        self.assertEqual([x["city"] for x in out["items"]],["Leiden","Amsterdam"])

    def test_older_than_30_days_hidden(self):
        self.put(days=31)
        self.assertEqual(catalog.query_listings("leiden","30d",connection=self.db,now=self.now)["count"],0)

    def test_today_is_first_seen_date_not_source_date(self):
        self.put(days=8,discovered_days=0)
        self.assertEqual(catalog.query_listings("leiden","today",connection=self.db,now=self.now)["count"],1)

    def test_other_market_rejected_can_qualify_here(self):
        self.put(status="REJECTED")
        self.assertEqual(catalog.query_listings("leiden","30d",connection=self.db,now=self.now)["count"],1)

    def test_excludes_expired_or_long_stay(self):
        self.put(stay={"mode":"fixed","start_date":"2020-01-01","end_date":"2020-03-01"})
        self.put(stay={"mode":"fixed","start_date":"2027-01-01","end_date":"2027-06-01"},url="https://example.org/other")
        self.assertEqual(catalog.query_listings("leiden","30d",connection=self.db,now=self.now)["count"],0)

    def test_alias_and_unsafe_url(self):
        self.assertEqual(catalog.city_key("'s-Gravenhage"),"den haag")
        self.assertIsNone(catalog.public_url("javascript:alert(1)"))

    def test_explicit_read_only_connection(self):
        self.put()
        with patch.dict(os.environ,{"SHORTSTAY_DB_PATH":str(self.file),"SHORTSTAY_TURSO_DATABASE_URL":"","SHORTSTAY_TURSO_AUTH_TOKEN":""}):
            self.assertEqual(catalog.query_listings("leiden","30d",now=self.now)["count"],1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM listings").fetchone()[0],1)

if __name__=="__main__":
    unittest.main()
