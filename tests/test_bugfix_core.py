"""Dependency-free checks for isolation, export packaging and anti-spam rules.

Run directly when Flask dependencies have not been installed yet:
    python tests/test_bugfix_core.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
import sys
import types
import unittest
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validation = load("expatus_bugfix_validation", ROOT / "expatus/services/validation.py")
strategy_engine = load("expatus_bugfix_strategy_engine", ROOT / "expatus/services/strategy_engine.py")

config_spec = importlib.util.spec_from_file_location(
    "expatus_bugfix_config", ROOT / "expatus/config.py"
)
config = importlib.util.module_from_spec(config_spec)
sys.modules[config_spec.name] = config
config_spec.loader.exec_module(config)


class ConfigurationTests(unittest.TestCase):
    def test_vercel_prefixed_turso_credentials_are_supported(self):
        environment = {
            "APP_ENV": "development",
            "DATABASE_BACKEND": "turso",
            "expatus_TURSO_DATABASE_URL": "libsql://prefixed.example",
            "expatus_TURSO_AUTH_TOKEN": "prefixed-token",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = config.load_settings()
        self.assertEqual(settings.turso_database_url, "libsql://prefixed.example")
        self.assertEqual(settings.turso_auth_token, "prefixed-token")

    def test_generic_turso_credentials_take_precedence(self):
        environment = {
            "APP_ENV": "development",
            "DATABASE_BACKEND": "turso",
            "TURSO_DATABASE_URL": "libsql://generic.example",
            "TURSO_AUTH_TOKEN": "generic-token",
            "expatus_TURSO_DATABASE_URL": "libsql://prefixed.example",
            "expatus_TURSO_AUTH_TOKEN": "prefixed-token",
        }
        with patch.dict(os.environ, environment, clear=True):
            settings = config.load_settings()
        self.assertEqual(settings.turso_database_url, "libsql://generic.example")
        self.assertEqual(settings.turso_auth_token, "generic-token")


class SpamValidationTests(unittest.TestCase):
    def test_normal_chinese_message_passes(self):
        validation.ensure_meaningful_message("海牙页面可以补充更多住房运营商。")

    def test_normal_english_message_passes(self):
        validation.ensure_meaningful_message("Please add more student housing resources.")

    def test_repeated_keyboard_message_is_rejected(self):
        with self.assertRaises(ValueError):
            validation.ensure_meaningful_message("asdasdasdasdasdasdasdasd")

    def test_short_keyboard_subject_is_rejected(self):
        for subject in ("fgjr", "gakki"):
            with self.subTest(subject=subject), self.assertRaises(ValueError):
                validation.ensure_meaningful_subject(subject)

    def test_useful_short_rental_subject_is_allowed(self):
        for subject in ("ROOM", "DUWO", "bug", "BSN"):
            with self.subTest(subject=subject):
                validation.ensure_meaningful_subject(subject)

    def test_fake_wechat_and_email_are_rejected(self):
        for email, wechat in (("", "asdasdasd"), ("asdasd@example.com", "")):
            with self.subTest(email=email, wechat=wechat), self.assertRaises(ValueError):
                validation.ensure_reasonable_contact(email, wechat)

    def test_normal_optional_contacts_are_allowed(self):
        validation.ensure_reasonable_contact("lin@example.com", "lintong_2026")


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.connection = sqlite3.connect(":memory:")
        cls.connection.row_factory = sqlite3.Row
        cls.connection.executescript(
            """
            CREATE TABLE properties(id INTEGER PRIMARY KEY,user_id INTEGER,name TEXT,source TEXT,
              rent REAL,url TEXT,status TEXT,is_ended INTEGER,end_reason TEXT,updated_at TEXT);
            CREATE TABLE favorites(user_id INTEGER,platform TEXT);
            CREATE TABLE strategy_generations(user_id INTEGER,identity_type TEXT,city TEXT,
              move_date TEXT,home_type TEXT,budget INTEGER,income_type TEXT,student_registration TEXT,
              university_housing TEXT,area_flexibility TEXT,result_summary TEXT,engine_version TEXT,
              result_json TEXT,created_at TEXT);
            CREATE TABLE contact_messages(user_id INTEGER,category TEXT,subject TEXT,message TEXT,
              email TEXT,wechat TEXT,created_at TEXT);
            CREATE TABLE case_submissions(user_id INTEGER,city TEXT,contract_date TEXT,rental_ended TEXT,
              moveout_date TEXT,base_rent REAL,deposit REAL,issues_json TEXT,checkin_report TEXT,
              deduction_spec TEXT,description TEXT,email TEXT,wechat TEXT,contact_ok INTEGER,created_at TEXT);
            CREATE TABLE audit_events(user_id INTEGER,event_type TEXT,outcome TEXT,
              details_json TEXT,created_at TEXT);
            """
        )
        modules = {}
        names = ("expatus", "expatus.constants", "expatus.database", "expatus.repositories", "expatus.repositories.properties",
                 "expatus.repositories.favorites", "expatus.services", "expatus.services.clock")
        cls.original_modules = {name: sys.modules.get(name) for name in names}
        for name in names:
            modules[name] = types.ModuleType(name)
            sys.modules[name] = modules[name]
        modules["expatus.database"].get_db = lambda: cls.connection
        modules["expatus.constants"].STATUSES = (
            "待处理", "已表达意向", "准备申请材料", "已提交申请", "已收到回复", "已预约看房", "已签约"
        )
        modules["expatus.repositories.properties"].list_for_user = lambda user: cls.connection.execute(
            "SELECT * FROM properties WHERE user_id=? ORDER BY id", (user,)
        ).fetchall()
        modules["expatus.repositories.properties"].serialize = lambda row: {
            "id": row["id"], "name": row["name"], "source": row["source"] or "",
            "rent": row["rent"], "url": row["url"] or "", "status": row["status"],
            "is_ended": bool(row["is_ended"]), "reason": row["end_reason"] or "",
        }
        modules["expatus.repositories.favorites"].names_for_user = lambda user: [
            row[0] for row in cls.connection.execute("SELECT platform FROM favorites WHERE user_id=?", (user,))
        ]
        modules["expatus.repositories"].properties = modules["expatus.repositories.properties"]
        modules["expatus.repositories"].favorites = modules["expatus.repositories.favorites"]
        modules["expatus.services.clock"].utcnow = lambda: datetime(2026, 8, 25, tzinfo=timezone.utc)
        cls.progress = load("expatus_bugfix_progress", ROOT / "expatus/services/progress_summary.py")
        cls.account = load("expatus_bugfix_account", ROOT / "expatus/services/account_data.py")

    @classmethod
    def tearDownClass(cls):
        cls.connection.close()
        for name, original in cls.original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def setUp(self):
        for table in ("properties", "favorites", "strategy_generations", "contact_messages",
                      "case_submissions", "audit_events"):
            self.connection.execute(f"DELETE FROM {table}")
        self.connection.commit()

    def insert_property(self, user, identifier, status, source="Pararius", ended=0):
        self.connection.execute(
            "INSERT INTO properties(id,user_id,name,source,rent,url,status,is_ended,end_reason,updated_at) "
            "VALUES(?,?,?,?,950,'https://example.test',?,?,NULL,'2026-08-25')",
            (identifier, user, f"Home {identifier}", source, status, ended),
        )

    def test_other_users_records_cannot_enter_summary(self):
        self.insert_property(1, 10, "已预约看房")
        self.insert_property(2, 20, "已签约", "ROOM.nl")
        result = self.progress.for_user(1)
        self.assertEqual(result["applications"], 1)
        self.assertEqual(result["replies"], 1)
        self.assertEqual(result["viewings"], 1)
        self.assertEqual(result["confirmed"], 0)
        self.assertEqual(result["mainChannel"], "commercial")

    def test_viewing_is_not_invented_for_submitted_application(self):
        self.insert_property(1, 10, "已提交申请")
        result = self.progress.for_user(1)
        self.assertEqual(result["viewings"], 0)
        self.assertEqual(result["replies"], 0)
        self.assertEqual(result["active"], 1)

    def test_reverting_current_status_removes_viewing(self):
        self.insert_property(1, 10, "已预约看房")
        self.assertEqual(self.progress.for_user(1)["viewings"], 1)
        self.connection.execute("UPDATE properties SET status='已提交申请' WHERE id=10")
        result = self.progress.for_user(1)
        self.assertEqual(result["viewings"], 0)
        self.assertEqual(result["replies"], 0)
        self.assertEqual(result["active"], 1)

    def test_ended_property_cannot_be_an_active_offer(self):
        self.insert_property(1, 10, "已提交申请", ended=1)
        self.assertEqual(self.progress.for_user(1)["active"], 0)

    def test_archive_contains_readable_csv_and_optional_json(self):
        self.insert_property(1, 10, "已收到回复")
        self.connection.execute("INSERT INTO favorites VALUES(1,'ROOM.nl')")
        user = {"id": 1, "email": "demo@expatus.test", "created_at": "2026-08-25",
                "verified_at": "2026-08-25", "privacy_acknowledged_at": "2026-08-25",
                "privacy_policy_version": "2026-08"}
        data = self.account.collect(user)
        with ZipFile(BytesIO(self.account.build_archive(data))) as archive:
            self.assertIn("01-房源进度.csv", archive.namelist())
            self.assertIn("07-完整数据.json", archive.namelist())
            csv_text = archive.read("01-房源进度.csv").decode("utf-8-sig")
            self.assertIn("房源,来源,月租", csv_text)
            self.assertIn("Home 10", csv_text)
            self.assertIn("ROOM.nl", archive.read("02-收藏平台.csv").decode("utf-8-sig"))

    def test_csv_formula_cells_are_escaped(self):
        self.assertEqual(self.account._safe_cell("=SUM(A1:A2)"), "'=SUM(A1:A2)")


class StrategyEngineTests(unittest.TestCase):
    PROFILE = {
        "identity": "master", "city": "Leiden", "moveDate": "2026-10-01",
        "homeType": "room", "budget": 900, "income": "none",
        "studentReg": "registered", "universityHousing": "waiting", "areaFlex": "yes",
    }

    def progress(self, **changes):
        value = {"applications": 0, "replies": 0, "viewings": 0, "active": 0,
                 "confirmed": 0, "mainChannel": "mixed", "tracked": 0}
        value.update(changes)
        return value

    def test_progress_changes_complete_backend_result(self):
        from datetime import date
        baseline = strategy_engine.generate(self.PROFILE, self.progress(), today=date(2026, 8, 26))
        stuck = strategy_engine.generate(
            self.PROFILE,
            self.progress(applications=15, active=15, tracked=15, mainChannel="commercial"),
            today=date(2026, 8, 26),
        )
        self.assertNotEqual(baseline["status"]["title"], stuck["status"]["title"])
        self.assertTrue(any(row["kind"] == "review" for row in stuck["effort"][1]["rows"]))
        self.assertEqual(stuck["channels"][2]["state"], "先检查转化")

    def test_viewing_reversion_changes_strategy(self):
        from datetime import date
        with_viewing = strategy_engine.generate(
            self.PROFILE, self.progress(applications=2, replies=2, viewings=2, active=2, tracked=2),
            today=date(2026, 8, 26),
        )
        reverted = strategy_engine.generate(
            self.PROFILE, self.progress(applications=2, active=2, tracked=2),
            today=date(2026, 8, 26),
        )
        self.assertNotEqual(with_viewing["status"]["title"], reverted["status"]["title"])
        self.assertEqual(reverted["progress"]["viewings"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
