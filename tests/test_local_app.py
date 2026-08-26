"""End-to-end Flask tests using an isolated, temporary SQLite database."""

from __future__ import annotations

import re
import sqlite3
import tempfile
import threading
import unittest
import urllib.request
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from werkzeug.serving import make_server
from werkzeug.security import generate_password_hash

from expatus import create_app
from expatus.database import get_db


PROFILE = {
    "identity": "master",
    "city": "Leiden",
    "moveDate": "2027-09-01",
    "homeType": "studio",
    "budget": 950,
    "income": "stipend",
    "studentReg": "registered",
    "universityHousing": "waiting",
    "areaFlex": "maybe",
}


class ExpatusAppTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary.name) / "expatus-test.db"
        self.app = create_app(
            {
                "environment": "development",
                "database_backend": "sqlite",
                "database_path": self.database_path,
                "demo_mode": True,
                "show_verification_code": True,
                "admin_password": "test-admin-password",
                "analytics_enabled": True,
                "cookie_secure": False,
                "enforce_canonical_host": True,
            }
        )
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def tearDown(self):
        self.temporary.cleanup()

    def csrf(self, path="/"):
        self.client.get(path)
        with self.client.session_transaction() as session:
            return session["_csrf"]

    def post_json(self, path, payload, *, method="post", csrf=None):
        token = csrf or self.csrf()
        return getattr(self.client, method)(
            path,
            json=payload,
            headers={"X-CSRF-Token": token},
        )

    def login_demo(self):
        response = self.post_json(
            "/api/auth/login", {"email": "demo@expatus.test", "password": "expatus123"}
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return response

    def admin_login(self):
        token = self.csrf("/admin/login")
        response = self.client.post(
            "/admin/login",
            data={"_csrf": token, "password": "test-admin-password", "next": "/admin"},
        )
        self.assertEqual(response.status_code, 302)
        return response

    def test_all_public_pages_render_with_shared_header_and_privacy(self):
        public_paths = [
            "/",
            "/auth",
            "/city/leiden",
            "/city/den-haag",
            "/rental-channels",
            "/housing-strategy",
            "/rental-materials",
            "/housing-plan-b",
            "/deposit-return-netherlands.html",
            "/contact",
            "/privacy",
        ]
        for path in public_paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn("隐私声明", response.get_data(as_text=True))
                self.assertIn("X-Content-Type-Options", response.headers)

    def test_www_canonical_sitemap_and_apex_redirect(self):
        homepage = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="https://www.expatus.nl/"', homepage)
        self.assertNotIn('href="https://expatus.nl/', homepage)
        sitemap = self.client.get("/sitemap.xml").get_data(as_text=True)
        self.assertIn("https://www.expatus.nl/city/leiden", sitemap)
        self.assertNotIn("/workspace/strategy", sitemap)
        robots = self.client.get("/robots.txt").get_data(as_text=True)
        self.assertIn("Sitemap: https://www.expatus.nl/sitemap.xml", robots)
        redirected = self.client.get("/city/leiden?q=huizen", headers={"Host": "expatus.nl"})
        self.assertEqual(redirected.status_code, 301)
        self.assertEqual(redirected.headers["Location"], "https://www.expatus.nl/city/leiden?q=huizen")

    def test_old_page_addresses_redirect_and_local_preview_exists(self):
        aliases = {
            "/leiden-rental-guide.html": "/city/leiden",
            "/den-haag-rental-guide.html": "/city/den-haag",
            "/housing-market.html": "/rental-channels",
            "/plan-b.html": "/housing-plan-b",
            "/leiden-rental-guide/": "/city/leiden",
            "/deposit-return-netherlands/": "/deposit-return-netherlands.html",
        }
        for original, destination in aliases.items():
            with self.subTest(path=original):
                response = self.client.get(original)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response.headers["Location"], destination)
        self.assertEqual(self.client.get("/preview-pages").status_code, 200)

    def test_local_analytics_remains_disabled_even_if_flag_is_set(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-analytics-enabled="false"', page)
        self.assertNotIn("https://www.googletagmanager.com/gtag/js", page)

    def test_private_pages_require_login_and_are_not_indexable(self):
        for path in ("/progress", "/favorites", "/workspace/strategy", "/account/data"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/auth?next=", response.headers["Location"])
                self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(self.client.get("/api/account/export").status_code, 401)
        self.assertEqual(self.client.get("/api/properties/summary").status_code, 401)

    def test_personal_workspace_navigation_only_appears_after_login(self):
        signed_out = self.client.get("/").get_data(as_text=True)
        self.assertNotIn('<summary>个人工作台</summary>', signed_out)
        self.assertNotIn('<span class="menu-group-label">个人工作台</span>', signed_out)
        self.assertIn("注册 / 登录", signed_out)
        self.login_demo()
        signed_in = self.client.get("/").get_data(as_text=True)
        self.assertIn('<summary>个人工作台</summary>', signed_in)
        self.assertIn('<span class="menu-group-label">个人工作台</span>', signed_in)
        self.assertIn('href="/account/data"', signed_in)

    def test_csrf_is_required_for_every_write(self):
        response = self.client.post(
            "/api/auth/login", json={"email": "demo@expatus.test", "password": "expatus123"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("页面验证", response.get_json()["error"])

    def test_registration_requires_privacy_acknowledgement_and_verifies_email(self):
        token = self.csrf("/auth")
        payload = {"email": "new.user@example.test", "password": "very-secure-password"}
        rejected = self.post_json("/api/auth/register/start", payload, csrf=token)
        self.assertEqual(rejected.status_code, 400)
        started = self.post_json(
            "/api/auth/register/start", {**payload, "privacy_acknowledged": True}, csrf=token
        )
        self.assertEqual(started.status_code, 200, started.get_json())
        code = started.get_json()["dev_code"]
        self.assertTrue(re.fullmatch(r"\d{6}", code))
        verified = self.post_json("/api/auth/register/verify", {"code": code}, csrf=token)
        self.assertEqual(verified.status_code, 200)
        self.assertEqual(verified.get_json()["redirect"], "/workspace/strategy")
        with self.app.app_context():
            account = get_db().execute(
                "SELECT * FROM users WHERE email=?", (payload["email"],)
            ).fetchone()
            self.assertTrue(account["privacy_acknowledged_at"])
            self.assertNotIn(payload["password"], account["password_hash"])
            stored_code = get_db().execute(
                "SELECT code_hash FROM verification_codes WHERE email=?", (payload["email"],)
            ).fetchone()["code_hash"]
            self.assertNotIn(code, stored_code)

    def test_existing_account_is_prompted_to_acknowledge_privacy(self):
        with self.app.app_context():
            get_db().execute(
                "INSERT INTO users(email,password_hash,verified_at,created_at) VALUES(?,?,?,?)",
                (
                    "legacy@example.test",
                    generate_password_hash("legacy-password"),
                    "2026-08-20T12:00:00+00:00",
                    "2026-08-20T12:00:00+00:00",
                ),
            )
            get_db().commit()
        result = self.post_json(
            "/api/auth/login", {"email": "legacy@example.test", "password": "legacy-password"}
        )
        destination = result.get_json()["redirect"]
        self.assertIn("/privacy?acknowledge=1", destination)
        notice = self.client.get(destination)
        self.assertIn("请先了解账户数据如何使用", notice.get_data(as_text=True))
        response = self.client.post(
            "/api/account/privacy/acknowledge",
            data={"_csrf": self.csrf(destination), "next": "/workspace/strategy"},
        )
        self.assertEqual(response.headers["Location"], "/workspace/strategy")
        with self.app.app_context():
            row = get_db().execute(
                "SELECT privacy_acknowledged_at FROM users WHERE email=?", ("legacy@example.test",)
            ).fetchone()
            self.assertTrue(row["privacy_acknowledged_at"])

    def test_login_failure_and_success_are_logged_without_raw_ip(self):
        denied = self.post_json(
            "/api/auth/login", {"email": "demo@expatus.test", "password": "incorrect"}
        )
        self.assertEqual(denied.status_code, 401)
        self.login_demo()
        with self.app.app_context():
            rows = get_db().execute(
                "SELECT event_type,ip_hash,details_json FROM audit_events ORDER BY id"
            ).fetchall()
            self.assertEqual([row["event_type"] for row in rows], ["login_failed", "login_success"])
            self.assertTrue(all(len(row["ip_hash"]) == 64 for row in rows))
            self.assertNotIn("incorrect", str([dict(row) for row in rows]))

    def test_property_lifecycle_and_workspace_strategy_summary(self):
        self.login_demo()
        created = self.post_json(
            "/api/properties",
            {"name": "Leiden Studio", "source": "Pararius", "rent": "950", "url": "https://example.test/home"},
        )
        self.assertEqual(created.status_code, 200)
        property_id = created.get_json()["property"]["id"]
        status = self.post_json(
            f"/api/properties/{property_id}/status", {"status": "已提交申请"}, method="patch"
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(self.post_json("/api/strategies/generate", PROFILE).status_code, 200)
        strategy_page = self.client.get("/workspace/strategy").get_data(as_text=True)
        self.assertRegex(strategy_page, r'"applications"\s*:\s*1')
        ended = self.post_json(f"/api/properties/{property_id}/end", {"reason": "房源已出租"})
        self.assertEqual(ended.status_code, 200)
        restored = self.post_json(f"/api/properties/{property_id}/restore", {})
        self.assertEqual(restored.status_code, 200)
        deleted = self.post_json(f"/api/properties/{property_id}", {}, method="delete")
        self.assertEqual(deleted.status_code, 200)

    def test_favorites_persist_and_reject_unknown_platforms(self):
        self.login_demo()
        saved = self.post_json("/api/favorites/toggle", {"platform": "ROOM.nl"})
        self.assertTrue(saved.get_json()["favorite"])
        page = self.client.get("/favorites").get_data(as_text=True)
        self.assertIn("ROOM.nl", page)
        self.assertIn('class="platform-avatar expatus-avatar--room"', page)
        self.assertNotIn("expatus-avatar--dynamic", page)
        rejected = self.post_json("/api/favorites/toggle", {"platform": "Unknown scam platform"})
        self.assertEqual(rejected.status_code, 400)
        removed = self.post_json("/api/favorites/toggle", {"platform": "ROOM.nl"})
        self.assertFalse(removed.get_json()["favorite"])

    def test_every_favorite_reuses_the_homepage_avatar_class(self):
        self.login_demo()
        self.post_json("/api/favorites/toggle", {"platform": "DUWO"})
        self.post_json("/api/favorites/toggle", {"platform": "Nestpick"})
        page = self.client.get("/favorites").get_data(as_text=True)
        self.assertIn('class="platform-avatar expatus-avatar--duwo"', page)
        self.assertIn('class="platform-avatar expatus-avatar--neste"', page)

    def test_progress_summary_uses_only_current_users_actual_statuses(self):
        self.login_demo()
        first = self.post_json("/api/properties", {"name": "My viewing", "source": "Pararius"})
        second = self.post_json("/api/properties", {"name": "My offer", "source": "Pararius"})
        self.post_json(
            f"/api/properties/{first.get_json()['property']['id']}/status",
            {"status": "已预约看房"},
            method="patch",
        )
        self.post_json(
            f"/api/properties/{second.get_json()['property']['id']}/status",
            {"status": "已提交申请"},
            method="patch",
        )
        with self.app.app_context():
            db = get_db()
            other = db.execute(
                "INSERT INTO users(email,password_hash,verified_at,created_at) VALUES(?,?,?,?)",
                ("other@example.test", generate_password_hash("secure-password"),
                 "2026-08-20T12:00:00+00:00", "2026-08-20T12:00:00+00:00"),
            ).lastrowid
            for index in range(5):
                db.execute(
                    "INSERT INTO properties(user_id,name,source,status,is_ended,created_at,updated_at) "
                    "VALUES(?,?,?,'已签约',0,?,?)",
                    (other, f"Someone else's home {index}", "ROOM.nl",
                     "2026-08-20T12:00:00+00:00", "2026-08-20T12:00:00+00:00"),
                )
            db.commit()

        response = self.client.get("/api/properties/summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "private, no-store")
        summary = response.get_json()["summary"]
        self.assertEqual(summary["applications"], 2)
        self.assertEqual(summary["replies"], 1)
        self.assertEqual(summary["viewings"], 1)
        self.assertEqual(summary["active"], 2)
        self.assertEqual(summary["confirmed"], 0)
        self.assertEqual(summary["mainChannel"], "commercial")
        self.assertEqual(self.post_json("/api/strategies/generate", PROFILE).status_code, 200)
        page = self.client.get("/workspace/strategy").get_data(as_text=True)
        self.assertRegex(page, r'"tracked"\s*:\s*2')
        self.assertNotIn('id="progressDialog"', page)

    def test_reverting_viewing_recalculates_backend_strategy(self):
        self.login_demo()
        generated = self.post_json("/api/strategies/generate", PROFILE)
        self.assertEqual(generated.status_code, 200)
        created = self.post_json("/api/properties", {"name": "Viewed apartment", "source": "Funda"})
        identifier = created.get_json()["property"]["id"]
        self.post_json(
            f"/api/properties/{identifier}/status", {"status": "已预约看房"}, method="patch"
        )
        before = self.client.get("/api/strategies/current").get_json()["strategy"]
        self.assertEqual(before["progress"]["viewings"], 1)
        self.post_json(
            f"/api/properties/{identifier}/status", {"status": "已提交申请"}, method="patch"
        )
        after = self.client.get("/api/strategies/current").get_json()["strategy"]
        self.assertEqual(after["progress"]["applications"], 1)
        self.assertEqual(after["progress"]["replies"], 0)
        self.assertEqual(after["progress"]["viewings"], 0)
        self.assertEqual(after["progress"]["active"], 1)
        self.assertNotEqual(before["status"]["title"], after["status"]["title"])

    def test_ended_offer_no_longer_appears_as_active(self):
        self.login_demo()
        created = self.post_json("/api/properties", {"name": "Old offer", "source": "Funda"})
        identifier = created.get_json()["property"]["id"]
        self.post_json(
            f"/api/properties/{identifier}/status", {"status": "已提交申请"}, method="patch"
        )
        self.assertEqual(self.client.get("/api/properties/summary").get_json()["summary"]["active"], 1)
        self.post_json(f"/api/properties/{identifier}/end", {"reason": "被拒绝"})
        summary = self.client.get("/api/properties/summary").get_json()["summary"]
        self.assertEqual(summary["applications"], 1)
        self.assertEqual(summary["active"], 0)

    def test_strategy_generation_persists_and_is_limited_server_side(self):
        self.login_demo()
        for expected in range(1, 4):
            response = self.post_json("/api/strategies/generate", PROFILE)
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.get_json()["used_today"], expected)
            self.assertEqual(response.get_json()["strategy"]["engine_version"], "strategy-v2-backend-2026-08-26")
        limited = self.post_json("/api/strategies/generate", PROFILE)
        self.assertEqual(limited.status_code, 429)
        page = self.client.get("/workspace/strategy").get_data(as_text=True)
        self.assertRegex(page, r'"used_today"\s*:\s*3')
        self.assertIn('"identity": "master"', page)
        with self.app.app_context():
            row = get_db().execute(
                "SELECT COUNT(*) AS total,MAX(engine_version) AS engine_version,MAX(result_json) AS result_json "
                "FROM strategy_generations"
            ).fetchone()
            count = row["total"]
            self.assertEqual(count, 3)
            self.assertEqual(row["engine_version"], "strategy-v2-backend-2026-08-26")
            self.assertIn('"channels"', row["result_json"])

    def test_strategy_rejects_invalid_choices(self):
        self.login_demo()
        invalid = self.post_json("/api/strategies/generate", {**PROFILE, "city": "<script>alert(1)</script>"})
        self.assertEqual(invalid.status_code, 400)
        bad_budget = self.post_json("/api/strategies/generate", {**PROFILE, "budget": 50})
        self.assertEqual(bad_budget.status_code, 400)

    def test_contact_honeypot_scripts_and_links_are_blocked(self):
        honeypot = self.post_json(
            "/api/contact", {"message": "automated advertising", "website": "https://spam.test"}
        )
        self.assertEqual(honeypot.status_code, 200)
        malicious = self.post_json("/api/contact", {"message": "<script>alert('x')</script>"})
        self.assertEqual(malicious.status_code, 400)
        many_links = self.post_json(
            "/api/contact",
            {"message": "https://a.test https://b.test https://c.test https://d.test"},
        )
        self.assertEqual(many_links.status_code, 400)
        legitimate = self.post_json(
            "/api/contact",
            {"category": "网站建议", "subject": "改进建议", "message": "这个网站帮助我整理了找房步骤。"},
        )
        self.assertEqual(legitimate.status_code, 200)
        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) AS total FROM contact_messages").fetchone()["total"]
            self.assertEqual(count, 1)

    def test_random_keyboard_content_and_fake_contact_details_never_reach_database(self):
        junk = (
            {"subject": "gakki", "message": "asdasdasdasdasdasdasdasdasd"},
            {"subject": "fgjr", "message": "垃圾信息还是没有消除"},
            {"message": "正常留言：我想反馈莱顿页面的问题。", "wechat": "asdasdasd"},
            {"message": "正常留言：我想反馈莱顿页面的问题。", "email": "asdasd@example.com"},
        )
        for item in junk:
            with self.subTest(item=item):
                response = self.post_json("/api/contact", item)
                self.assertEqual(response.status_code, 400, response.get_json())
        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) FROM contact_messages").fetchone()[0]
            self.assertEqual(count, 0)

    def test_meaningful_chinese_and_english_messages_are_accepted(self):
        chinese = self.post_json(
            "/api/contact",
            {"subject": "海牙页面建议", "message": "海牙页面可以补充更多住房运营商。"},
        )
        self.assertEqual(chinese.status_code, 200, chinese.get_json())
        english = self.post_json(
            "/api/contact",
            {"subject": "Website feedback", "message": "Please add more student housing resources."},
        )
        self.assertEqual(english.status_code, 200, english.get_json())

    def test_rental_case_is_stored_with_explicit_contact_preference(self):
        response = self.post_json(
            "/api/cases",
            {
                "city": "Leiden",
                "description": "房东退租后没有在约定时间说明押金扣款情况。",
                "issues": ["押金未退"],
                "base_rent": "950",
                "deposit": "1900",
                "contact_ok": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            row = get_db().execute("SELECT city,contact_ok FROM case_submissions").fetchone()
            self.assertEqual(row["city"], "Leiden")
            self.assertEqual(row["contact_ok"], 0)

    def test_admin_dashboard_logs_users_strategies_and_csv(self):
        self.login_demo()
        self.post_json("/api/strategies/generate", PROFILE)
        self.post_json(
            "/api/contact",
            {"subject": "=后台导出测试", "message": "这是需要在后台显示的正常留言。"},
        )
        self.admin_login()
        for path in ("/admin", "/admin/users", "/admin/activity", "/admin/strategies", "/admin/messages", "/admin/cases"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")
        users_page = self.client.get("/admin/users").get_data(as_text=True)
        self.assertIn("demo@expatus.test", users_page)
        export = self.client.get("/admin/messages.csv")
        self.assertIn("'=后台导出测试", export.get_data(as_text=True))
        public_while_admin = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-analytics-enabled="false"', public_while_admin)

    def test_account_export_and_deletion_remove_associated_records(self):
        self.login_demo()
        self.post_json("/api/favorites/toggle", {"platform": "ROOM.nl"})
        self.post_json("/api/strategies/generate", PROFILE)
        self.post_json("/api/contact", {"message": "这是一条应出现在个人数据导出中的留言。"})
        exported = self.client.get("/api/account/export?format=json")
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.get_json()["account"]["email"], "demo@expatus.test")
        self.assertEqual(exported.get_json()["favorites"], ["ROOM.nl"])
        self.assertEqual(len(exported.get_json()["contact_messages"]), 1)
        self.assertTrue(exported.get_json()["account_activity"])
        deleted = self.post_json("/api/account", {}, method="delete")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/progress").status_code, 302)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM favorites").fetchone()[0], 0)
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM strategy_generations").fetchone()[0], 0)

    def test_account_data_page_and_downloadable_archive_are_readable(self):
        self.login_demo()
        self.post_json("/api/favorites/toggle", {"platform": "ROOM.nl"})
        self.post_json("/api/properties", {"name": "Leiden Studio", "source": "Pararius"})
        page = self.client.get("/account/data")
        self.assertEqual(page.status_code, 200)
        self.assertIn("我的账户数据", page.get_data(as_text=True))
        self.assertIn("Leiden Studio", page.get_data(as_text=True))
        self.assertIn("ROOM.nl", page.get_data(as_text=True))
        self.assertEqual(page.headers["X-Robots-Tag"], "noindex, nofollow")

        exported = self.client.get("/api/account/export")
        self.assertEqual(exported.mimetype, "application/zip")
        self.assertIn("expatus-personal-data.zip", exported.headers["Content-Disposition"])
        with ZipFile(BytesIO(exported.data)) as archive:
            self.assertIn("00-账户说明.txt", archive.namelist())
            self.assertIn("01-房源进度.csv", archive.namelist())
            self.assertIn("07-完整数据.json", archive.namelist())
            self.assertIn("房源,来源,月租", archive.read("01-房源进度.csv").decode("utf-8-sig"))
            self.assertIn("ROOM.nl", archive.read("02-收藏平台.csv").decode("utf-8-sig"))

    def test_rate_limiting_blocks_repeated_contact_submissions(self):
        for index in range(5):
            result = self.post_json("/api/contact", {"message": f"正常测试留言，第 {index} 条。"})
            self.assertEqual(result.status_code, 200)
        blocked = self.post_json("/api/contact", {"message": "第六条留言应当触发限流。"})
        self.assertEqual(blocked.status_code, 429)


class LegacyMigrationTests(unittest.TestCase):
    def test_existing_accounts_and_rental_records_survive_additive_migration(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "legacy.db"
            connection = sqlite3.connect(database)
            connection.executescript(
                """
                CREATE TABLE users(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT NOT NULL UNIQUE,
                  password_hash TEXT,verified_at TEXT NOT NULL,created_at TEXT NOT NULL
                );
                CREATE TABLE pending_registrations(
                  email TEXT PRIMARY KEY,password_hash TEXT NOT NULL,
                  created_at TEXT NOT NULL,updated_at TEXT NOT NULL
                );
                CREATE TABLE properties(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,
                  name TEXT NOT NULL,source TEXT,rent REAL,url TEXT,
                  status TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
                );
                INSERT INTO users(email,password_hash,verified_at,created_at)
                VALUES('existing@example.test','preserved-hash','2026-01-01','2026-01-01');
                INSERT INTO properties(user_id,name,status,created_at,updated_at)
                VALUES(1,'Existing Leiden room','申请中','2026-01-02','2026-01-02');
                """
            )
            connection.commit()
            connection.close()
            app = create_app(
                {"database_path": database, "database_backend": "sqlite", "demo_mode": False}
            )
            with app.app_context():
                row = get_db().execute("SELECT * FROM users WHERE id=1").fetchone()
                self.assertEqual(row["email"], "existing@example.test")
                self.assertEqual(row["password_hash"], "preserved-hash")
                self.assertIsNone(row["privacy_acknowledged_at"])
                property_row = get_db().execute("SELECT * FROM properties WHERE id=1").fetchone()
                self.assertEqual(property_row["name"], "Existing Leiden room")
                self.assertEqual(property_row["status"], "已提交申请")
                self.assertEqual(property_row["is_ended"], 0)


class HttpSmokeTests(unittest.TestCase):
    def test_real_http_server_serves_pages_styles_scripts_and_sitemap(self):
        with tempfile.TemporaryDirectory() as folder:
            app = create_app(
                {
                    "database_path": Path(folder) / "http-test.db",
                    "database_backend": "sqlite",
                    "demo_mode": False,
                }
            )
            server = make_server("127.0.0.1", 0, app)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                paths = (
                    "/",
                    "/city/den-haag",
                    "/privacy",
                    "/admin/login",
                    "/static/css/dist/index.css",
                    "/static/js/privacy-consent.js",
                    "/sitemap.xml",
                )
                for path in paths:
                    with self.subTest(path=path):
                        with urllib.request.urlopen(base + path, timeout=5) as response:
                            self.assertEqual(response.status, 200)
                            self.assertGreater(len(response.read()), 40)
            finally:
                server.shutdown()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
