import csv
import hashlib
import io
import json
import os
import re
import secrets
import smtplib
import sqlite3
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, Response, abort, g, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent


def load_env_file(path: Path):
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(BASE_DIR / ".env")

DB_PATH = Path(os.getenv("EXPATUS_DB", BASE_DIR / "data" / "expatus.db"))
TURSO_DATABASE_URL = (
    os.getenv("TURSO_DATABASE_URL")
    or os.getenv("expatus_TURSO_DATABASE_URL")
    or ""
).strip()

TURSO_AUTH_TOKEN = (
    os.getenv("TURSO_AUTH_TOKEN")
    or os.getenv("expatus_TURSO_AUTH_TOKEN")
    or ""
).strip()
BASE_URL = os.getenv("BASE_URL", "https://expatus.nl").rstrip("/")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
STATUSES = ["待处理", "已表达意向", "准备申请材料", "已提交申请", "已签约"]
PROGRESS_PERCENT = {"待处理": 0, "已表达意向": 20, "准备申请材料": 45, "已提交申请": 75, "已签约": 100}
STAGE_DESCRIPTIONS = {
    "待处理": "这套房源已经加入记录，可以从这里继续跟进。",
    "已表达意向": "已经通过消息、报名或其他方式对这套房源表达兴趣。",
    "准备申请材料": "这套房源已经进入申请材料准备阶段。",
    "已提交申请": "申请已经提交，目前等待后续结果。",
    "已签约": "这套房源已经完成签约。",
}
END_REASONS = ["房源已出租", "被拒绝", "无回复", "主动放弃", "其他"]
SOURCE_SUGGESTIONS = ["Pararius", "Funda", "Kamernet", "ROOM.nl", "DUWO", "HousingAnywhere", "Facebook 群", "微信群", "朋友介绍"]

PLATFORMS = [
    dict(name="ROOM.nl", initials="R", color="#355f49", type="student", type_label="学生住房", cities=["阿姆斯特丹","海牙","莱顿","代尔夫特","瓦赫宁根","其他城市"], city_text="莱顿、代尔夫特、阿姆斯特丹、海牙、瓦赫宁根等", price_band="low", price="约 €400-900/月", meta="一次性注册 €35", meta_class="fee", desc="多家社会学生住房机构共同使用的学生住房注册与申请平台。等待时间和申请方式会因城市、房源和资格条件而不同。", url="https://www.room.nl/"),
    dict(name="DUWO", initials="D", color="#2d5a3f", type="student", type_label="学生住房", cities=["阿姆斯特丹","海牙","莱顿","代尔夫特","瓦赫宁根","其他城市"], city_text="阿姆斯特丹、代尔夫特、海牙、莱顿、瓦赫宁根等", price_band="low", price="约 €400-900/月", meta="常通过 ROOM 申请", meta_class="fee", desc="荷兰大型学生住房机构。普通学生住房中有相当一部分通过 ROOM 申请，也有面向特定学校或项目的房源。", url="https://www.duwo.nl/"),
    dict(name="SSH", initials="SS", color="#4a7c59", type="student", type_label="学生住房", cities=["鹿特丹","乌特勒支","格罗宁根","蒂尔堡","其他城市"], city_text="乌特勒支、鹿特丹、蒂尔堡、格罗宁根、Zwolle、Amersfoort", price_band="low", price="约 €400-900/月", meta="Long Stay 常通过 ROOM", meta_class="fee", desc="学生住房机构，包含 Long Stay 和部分学校合作的 Short Stay。不同城市与学校对应的申请路径并不完全相同。", url="https://www.sshxl.nl/"),
    dict(name="Xior Student Housing", initials="X", color="#496f60", type="student", type_label="学生住房", cities=["阿姆斯特丹","鹿特丹","乌特勒支","海牙","莱顿","代尔夫特","埃因霍温","格罗宁根","马斯特里赫特","瓦赫宁根","其他城市"], city_text="莱顿、阿姆斯特丹、海牙、代尔夫特、埃因霍温、马斯特里赫特等", price_band="mid", price="约 €500-1,200+/月", meta="费用按项目", meta_class="note", desc="面向学生和年轻租客的住房运营商，在荷兰多个大学城市提供房间与 Studio，具体租期、家具和费用按项目不同。", url="https://www.xiorstudenthousing.eu/"),
    dict(name="Vestide", initials="V", color="#5a7a65", type="student", type_label="学生住房", cities=["埃因霍温"], city_text="埃因霍温", price_band="low", price="约 €400-900/月", meta="注册与分配规则以官网为准", meta_class="note", desc="埃因霍温本地重要的学生住房机构，提供学生房间与独立住房。部分房源会依据注册时间或特定分配规则提供。", url="https://rooms.vestide.nl/"),
    dict(name="Maastricht Housing", initials="MH", color="#476b5b", type="student", type_label="学生住房", cities=["马斯特里赫特"], city_text="马斯特里赫特", price_band="low", price="约 €400-1,000+/月", meta="一次性注册 €35", meta_class="fee", desc="马斯特里赫特面向学生和部分年轻租客的重要住房入口，汇集当地学生住房机构与私人房源。", url="https://maastrichthousing.com/"),
    dict(name="Holland2Stay", initials="H2", color="#5a9a6a", type="operator", type_label="住房运营商", cities=["阿姆斯特丹","鹿特丹","乌特勒支","海牙","莱顿","代尔夫特","埃因霍温","其他城市"], city_text="荷兰多个城市", price_band="mid", price="约 €700-1,500+/月", meta="订房时可能有 booking fee", meta_class="fee", desc="大型住房运营商，提供 furnished / unfurnished、短租与长租等不同项目。房源与申请资格按楼盘分别设置。", url="https://www.holland2stay.com/"),
    dict(name="Pararius", initials="P", color="#b18b62", type="general", type_label="综合租房", cities=["全部城市"], city_text="全荷兰", price_band="high", price="约 €900-2,000+/月", meta="浏览免费", meta_class="free", desc="荷兰大型独立租房网站，聚合大量由专业房产中介发布的公寓与住宅，可按城市、租金和房型筛选。", url="https://www.pararius.com/"),
    dict(name="Funda", initials="F", color="#b87a42", type="general", type_label="综合租房", cities=["全部城市"], city_text="全荷兰", price_band="high", price="约 €900-2,000+/月", meta="浏览免费", meta_class="free", desc="荷兰知名住宅平台，同时设有租房频道。私人市场中的公寓、住宅和中介房源较多，适合与 Pararius 交叉查看。", url="https://www.funda.nl/zoeken/huur/"),
    dict(name="Kamernet", initials="K", color="#9a7657", type="general", type_label="综合租房", cities=["全部城市"], city_text="全荷兰", price_band="mid", price="约 €500-1,200+/月", meta="联系多数房源需 Premium", meta_class="fee", desc="房间、Studio 和公寓较多，也常用于寻找合租室友。浏览房源较容易，但联系多数发布者通常需要 Premium。", url="https://kamernet.nl/en"),
    dict(name="Huurwoningen.nl", initials="HW", color="#8e775e", type="general", type_label="综合租房", cities=["全部城市"], city_text="全荷兰", price_band="high", price="约 €800-2,000+/月", meta="Premium 约 €29.95/月", meta_class="fee", desc="覆盖全荷兰的租房搜索网站，可按城市和租金筛选公寓、住宅与部分房间。Basic 可浏览，部分联系功能需要 Premium。", url="https://www.huurwoningen.nl/"),
    dict(name="HousingAnywhere", initials="HA", color="#587394", type="international", type_label="国际·中短租", cities=["全部城市"], city_text="荷兰主要城市", price_band="mid", price="约 €700-1,600+/月", meta="荷兰房源规则单独适用", meta_class="note", desc="面向国际学生和年轻职场人士的跨国租房平台，中短期 furnished 房源较多。荷兰房源的费用与联系规则需按当前页面确认。", url="https://housinganywhere.com/"),
    dict(name="Nestpick", initials="N", color="#61778d", type="international", type_label="国际·中短租", cities=["全部城市"], city_text="荷兰主要城市", price_band="high", price="约 €900-2,000+/月", meta="搜索免费", meta_class="free", desc="以 furnished 中长期住房为主的聚合搜索工具，会展示合作伙伴的房源并跳转至相应渠道完成后续申请。", url="https://www.nestpick.com/"),
    dict(name="Facebook 租房群", initials="FB", color="#765a82", type="community", type_label="合租·社群", cities=["全部城市"], city_text="各城市均有不同群组", price_band="mid", price="价格差异较大", meta="通常免费浏览", meta_class="free", desc="城市租房群、学生群和转租群里会出现房间与合租信息。来源分散、信息质量不一，需要自行核验发布者、合同和注册地址。", url="https://www.facebook.com/"),
    dict(name="Airbnb 月租", initials="A", color="#4f7088", type="international", type_label="国际·中短租", cities=["全部城市"], city_text="荷兰多数城市", price_band="high", price="通常 €1,000+/月", meta="短期过渡", meta_class="note", desc="更适合作为刚到荷兰、等待长期住房时的短期过渡选择。价格通常高于普通长期租赁，是否可注册地址需单独确认。", url="https://www.airbnb.com/"),
]
PLATFORM_BY_NAME = {p["name"]: p for p in PLATFORMS}

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = os.getenv("SECRET_KEY", "dev-only-change-me-before-deploy")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "0") == "1",
)
app.permanent_session_lifetime = timedelta(days=30)


def utcnow():
    return datetime.now(timezone.utc)


class CompatRow(dict):
    """Dict-like row that also supports SQLite-style numeric indexing."""
    def __init__(self, columns, values):
        self._values = tuple(values)
        super().__init__(zip(columns, self._values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class CompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def lastrowid(self):
        return getattr(self._cursor, "lastrowid", None)

    @property
    def rowcount(self):
        return getattr(self._cursor, "rowcount", -1)

    def _columns(self):
        description = getattr(self._cursor, "description", None) or []
        return [col[0] for col in description]

    def _convert(self, row):
        if row is None:
            return None
        if isinstance(row, dict):
            return CompatRow(list(row.keys()), list(row.values()))
        return CompatRow(self._columns(), row)

    def fetchone(self):
        return self._convert(self._cursor.fetchone())

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [self._convert(row) for row in rows]

    def __iter__(self):
        for row in self._cursor:
            yield self._convert(row)


class RemoteConnection:
    """Small compatibility layer so the existing sqlite3-style app code can use Turso."""
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql, params=()):
        return CompatCursor(self._connection.execute(sql, params))

    def executescript(self, script):
        # sqlite3.complete_statement lets us safely split the schema script.
        statement = ""
        for line in script.splitlines():
            statement += line + "\n"
            if sqlite3.complete_statement(statement):
                sql = statement.strip()
                if sql:
                    self.execute(sql)
                statement = ""
        if statement.strip():
            self.execute(statement.strip())
        return self

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        rollback = getattr(self._connection, "rollback", None)
        if rollback:
            return rollback()

    def close(self):
        return self._connection.close()


def open_db_connection():
    """Use Turso on Vercel/production when credentials exist; otherwise local SQLite."""
    if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
        if TURSO_DATABASE_URL.startswith("turso://"):
            import turso_serverless
            remote = turso_serverless.connect(
                TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )
        else:
            import libsql
            remote = libsql.connect(
                database=TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )
        conn = RemoteConnection(remote)
        # Keep behavior aligned with the original SQLite setup.
        try:
            conn.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass
        return conn

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def db():
    if "db" not in g:
        g.db = open_db_connection()
    return g.db


@app.teardown_appcontext
def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def column_names(conn, table):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def init_db():
    conn = open_db_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT,
        verified_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS pending_registrations(
        email TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS verification_codes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        purpose TEXT NOT NULL,
        code_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        used_at TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_codes_email_purpose ON verification_codes(email,purpose,created_at DESC);
    CREATE TABLE IF NOT EXISTS properties(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        source TEXT,
        rent REAL,
        url TEXT,
        status TEXT NOT NULL DEFAULT '待处理',
        is_ended INTEGER NOT NULL DEFAULT 0,
        end_reason TEXT,
        ended_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_properties_user ON properties(user_id,created_at DESC);
    CREATE TABLE IF NOT EXISTS favorites(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        platform TEXT NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id,platform)
    );
    CREATE TABLE IF NOT EXISTS case_submissions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        city TEXT,
        contract_date TEXT,
        rental_ended TEXT,
        moveout_date TEXT,
        base_rent REAL,
        deposit REAL,
        issues_json TEXT NOT NULL,
        checkin_report TEXT,
        deduction_spec TEXT,
        description TEXT NOT NULL,
        email TEXT,
        wechat TEXT,
        contact_ok INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS contact_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        category TEXT NOT NULL,
        subject TEXT,
        message TEXT NOT NULL,
        email TEXT,
        wechat TEXT,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_contact_messages_created ON contact_messages(created_at DESC);
    """)

    # Lightweight migration from the first local MVP if the same DB is reused.
    user_cols = column_names(conn, "users")
    if "password_hash" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    prop_cols = column_names(conn, "properties")
    if "is_ended" not in prop_cols:
        conn.execute("ALTER TABLE properties ADD COLUMN is_ended INTEGER NOT NULL DEFAULT 0")
    if "end_reason" not in prop_cols:
        conn.execute("ALTER TABLE properties ADD COLUMN end_reason TEXT")
    if "ended_at" not in prop_cols:
        conn.execute("ALTER TABLE properties ADD COLUMN ended_at TEXT")
    for old, new in {
        "待联系":"待处理", "已联系":"已表达意向", "准备申请":"准备申请材料", "申请中":"已提交申请"
    }.items():
        conn.execute("UPDATE properties SET status=? WHERE status=?", (new, old))

    if os.getenv("DEMO_MODE", "1") == "1":
        email = "demo@expatus.test"
        row = conn.execute("SELECT id,password_hash FROM users WHERE email=?", (email,)).fetchone()
        now = utcnow().isoformat()
        pw_hash = generate_password_hash("expatus123")
        if row:
            if not row[1]:
                conn.execute("UPDATE users SET password_hash=? WHERE id=?", (pw_hash, row[0]))
        else:
            conn.execute("INSERT INTO users(email,password_hash,verified_at,created_at) VALUES(?,?,?,?)", (email,pw_hash,now,now))
    conn.commit()
    conn.close()


_db_initialized = False


def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


def csrf_token():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        session["_csrf"] = token
    return token


app.jinja_env.globals.update(csrf_token=csrf_token, BASE_URL=BASE_URL)


@app.before_request
def load_user_and_csrf():
    ensure_db_initialized()
    g.user = None
    uid = session.get("user_id")
    if uid:
        g.user = db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not g.user:
            session.pop("user_id", None)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        supplied = request.headers.get("X-CSRF-Token") or request.form.get("_csrf") or ""
        expected = session.get("_csrf") or ""
        if not expected or not secrets.compare_digest(str(supplied), str(expected)):
            if request.path.startswith("/api/"):
                return jsonify(ok=False, error="页面验证信息已失效，请刷新页面后重试。"), 400
            abort(400)


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            target = request.full_path if request.query_string else request.path
            return redirect(url_for("auth", next=target))
        return view(*args, **kwargs)
    return wrapper


def api_login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not g.user:
            return jsonify(ok=False, error="请先登录。", login_url=url_for("auth", next=request.referrer or "/")), 401
        return view(*args, **kwargs)
    return wrapper


def safe_next(value):
    if not value:
        return "/"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return "/"
    return value



def admin_enabled():
    return bool(os.getenv("ADMIN_PASSWORD", "").strip())


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("admin_authenticated"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


def case_row_dict(row):
    item = dict(row)
    try:
        item["issues"] = json.loads(item.get("issues_json") or "[]")
    except Exception:
        item["issues"] = []
    return item


def message_row_dict(row):
    return dict(row)

def normalize_email(value):
    return (value or "").strip().lower()


def masked_email(email):
    local, _, domain = email.partition("@")
    head = local[: min(3, len(local))]
    return f"{head}{'***' if len(local) > 3 else ''}@{domain}"


def code_hash(email, purpose, code):
    return hashlib.sha256(f"{app.secret_key}:{purpose}:{email}:{code}".encode("utf-8")).hexdigest()


def send_verification_code(email, purpose):
    now = utcnow()
    last = db().execute(
        "SELECT created_at FROM verification_codes WHERE email=? AND purpose=? ORDER BY id DESC LIMIT 1",
        (email, purpose),
    ).fetchone()
    if last and now - datetime.fromisoformat(last["created_at"]) < timedelta(seconds=60):
        raise ValueError("请等待约 60 秒后再重新发送验证码。")
    count = db().execute(
        "SELECT COUNT(*) c FROM verification_codes WHERE email=? AND purpose=? AND created_at>=?",
        (email, purpose, (now - timedelta(hours=1)).isoformat()),
    ).fetchone()["c"]
    if count >= 5:
        raise ValueError("这个邮箱一小时内发送次数过多，请稍后再试。")

    demo = os.getenv("DEMO_MODE", "1") == "1" and email == "demo@expatus.test"
    code = "123456" if demo else f"{secrets.randbelow(1_000_000):06d}"
    # Sending a new code invalidates previous unused codes for the same purpose.
    db().execute("UPDATE verification_codes SET used_at=? WHERE email=? AND purpose=? AND used_at IS NULL", (now.isoformat(), email, purpose))
    db().execute(
        "INSERT INTO verification_codes(email,purpose,code_hash,expires_at,created_at) VALUES(?,?,?,?,?)",
        (email, purpose, code_hash(email, purpose, code), (now + timedelta(minutes=10)).isoformat(), now.isoformat()),
    )
    db().commit()

    host = os.getenv("SMTP_HOST")
    if not host:
        print(f"[Expatus dev] {purpose} code for {email}: {code}")
        return code if os.getenv("DEV_SHOW_VERIFICATION_CODE", "1") == "1" else None

    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "")
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM", username)
    subject = "Expatus 邮箱验证码" if purpose == "register" else "Expatus 重置密码验证码"
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = email
    msg.set_content(f"你的 Expatus 验证码是：{code}\n\n验证码 10 分钟内有效。如果不是你本人操作，请忽略这封邮件。")
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if os.getenv("SMTP_STARTTLS", "1") == "1":
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(msg)
    return None


def verify_code(email, purpose, code):
    row = db().execute(
        "SELECT * FROM verification_codes WHERE email=? AND purpose=? AND used_at IS NULL ORDER BY id DESC LIMIT 1",
        (email, purpose),
    ).fetchone()
    if not row:
        return False, "验证码不存在或已失效，请重新获取。"
    if row["attempts"] >= 5:
        return False, "验证码错误次数过多，请重新获取。"
    if datetime.fromisoformat(row["expires_at"]) < utcnow():
        return False, "验证码已过期，请重新获取。"
    if not (len(code) == 6 and code.isdigit()) or not secrets.compare_digest(row["code_hash"], code_hash(email, purpose, code)):
        db().execute("UPDATE verification_codes SET attempts=attempts+1 WHERE id=?", (row["id"],))
        db().commit()
        return False, "验证码不正确，请重新输入。"
    now = utcnow().isoformat()
    db().execute("UPDATE verification_codes SET used_at=? WHERE id=?", (now, row["id"]))
    db().commit()
    return True, None


def parse_money(value):
    if value in (None, ""):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError("金额格式不正确。")
    if number < 0 or number > 1000000:
        raise ValueError("金额格式不正确。")
    return number


def valid_http_url(value):
    if not value:
        return True
    p = urlparse(value)
    return p.scheme in {"http", "https"} and bool(p.netloc)


def property_dict(row):
    return {
        "id": row["id"], "name": row["name"], "source": row["source"] or "", "rent": row["rent"], "url": row["url"] or "",
        "status": row["status"], "is_ended": bool(row["is_ended"]), "reason": row["end_reason"] or "",
    }


# ---------- Public pages ----------
@app.get("/")
def home():
    favorites = []
    if g.user:
        favorites = [r["platform"] for r in db().execute("SELECT platform FROM favorites WHERE user_id=? ORDER BY created_at", (g.user["id"],)).fetchall()]
    return render_template("home.html", user=g.user, platforms=PLATFORMS, favorites=favorites)


@app.get("/auth")
def auth():
    if g.user:
        return redirect(safe_next(request.args.get("next")) or url_for("progress"))
    return render_template("auth.html", user=None, next_url=safe_next(request.args.get("next")))


@app.get("/progress")
@login_required
def progress():
    rows = db().execute("SELECT * FROM properties WHERE user_id=? ORDER BY is_ended ASC, updated_at DESC, id DESC", (g.user["id"],)).fetchall()
    return render_template(
        "progress.html", user=g.user, properties=[property_dict(r) for r in rows], statuses=STATUSES,
        progress_percent=PROGRESS_PERCENT, stage_descriptions=STAGE_DESCRIPTIONS, sources=SOURCE_SUGGESTIONS, end_reasons=END_REASONS,
    )


@app.get("/favorites")
@login_required
def favorites_page():
    names = [r["platform"] for r in db().execute("SELECT platform FROM favorites WHERE user_id=? ORDER BY created_at DESC", (g.user["id"],)).fetchall()]
    platforms = [PLATFORM_BY_NAME[n] for n in names if n in PLATFORM_BY_NAME]
    return render_template("favorites.html", user=g.user, platforms=platforms)


@app.get("/city/leiden")
def leiden():
    return render_template("leiden.html", user=g.user)


@app.get("/deposit-return-netherlands.html")
def deposit():
    return render_template("deposit.html", user=g.user)


@app.get("/contact")
def contact():
    return render_template("contact.html", user=g.user)


@app.get("/robots.txt")
def robots():
    content = f"User-agent: *\nAllow: /\n\nSitemap: {BASE_URL}/sitemap.xml\n"
    return Response(content, mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    urls = [
        (f"{BASE_URL}/", "weekly", "1.0"),
        (f"{BASE_URL}/city/leiden", "monthly", "0.8"),
        (f"{BASE_URL}/deposit-return-netherlands.html", "monthly", "0.8"),
        (f"{BASE_URL}/contact", "yearly", "0.3"),
    ]
    items = "".join(f"<url><loc>{u}</loc><changefreq>{freq}</changefreq><priority>{prio}</priority></url>" for u, freq, prio in urls)
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{items}</urlset>', mimetype="application/xml")



# ---------- Lightweight admin: research submissions ----------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    configured = admin_enabled()
    error = None
    if request.method == "POST":
        provided = str(request.form.get("password") or "")
        expected = os.getenv("ADMIN_PASSWORD", "")
        if expected and secrets.compare_digest(provided, expected):
            session["admin_authenticated"] = True
            session.permanent = True
            csrf_token()
            return redirect(safe_next(request.form.get("next") or "/admin/cases"))
        error = "后台密码不正确。"
    return render_template(
        "admin_login.html",
        user=g.user,
        auth_simple_nav=True,
        error=error,
        configured=configured,
        next_url=safe_next(request.args.get("next") or request.form.get("next") or "/admin/cases"),
    )


@app.post("/admin/logout")
def admin_logout():
    session.pop("admin_authenticated", None)
    return redirect(url_for("admin_login"))


@app.get("/admin/cases")
@admin_required
def admin_cases():
    rows = db().execute(
        "SELECT * FROM case_submissions ORDER BY created_at DESC, id DESC LIMIT 500"
    ).fetchall()
    cases = [case_row_dict(r) for r in rows]
    total = db().execute("SELECT COUNT(*) c FROM case_submissions").fetchone()["c"]
    contactable = db().execute(
        "SELECT COUNT(*) c FROM case_submissions WHERE contact_ok=1 AND (email IS NOT NULL OR wechat IS NOT NULL)"
    ).fetchone()["c"]
    return render_template(
        "admin_cases.html",
        user=g.user,
        auth_simple_nav=True,
        cases=cases,
        total=total,
        contactable=contactable,
    )


@app.get("/admin/cases.csv")
@admin_required
def admin_cases_csv():
    rows = db().execute(
        "SELECT * FROM case_submissions ORDER BY created_at DESC, id DESC"
    ).fetchall()
    output = io.StringIO()
    fields = [
        "id", "city", "contract_date", "rental_ended", "moveout_date",
        "base_rent", "deposit", "issues", "checkin_report", "deduction_spec",
        "description", "email", "wechat", "contact_ok", "created_at"
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        item = case_row_dict(row)
        writer.writerow({
            "id": item.get("id"),
            "city": item.get("city") or "",
            "contract_date": item.get("contract_date") or "",
            "rental_ended": item.get("rental_ended") or "",
            "moveout_date": item.get("moveout_date") or "",
            "base_rent": item.get("base_rent") if item.get("base_rent") is not None else "",
            "deposit": item.get("deposit") if item.get("deposit") is not None else "",
            "issues": "、".join(item.get("issues") or []),
            "checkin_report": item.get("checkin_report") or "",
            "deduction_spec": item.get("deduction_spec") or "",
            "description": item.get("description") or "",
            "email": item.get("email") or "",
            "wechat": item.get("wechat") or "",
            "contact_ok": "是" if item.get("contact_ok") else "否",
            "created_at": item.get("created_at") or "",
        })
    data = "\ufeff" + output.getvalue()
    return Response(
        data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="expatus-case-submissions.csv"'},
    )



@app.get("/admin/messages")
@admin_required
def admin_messages():
    rows = db().execute(
        "SELECT * FROM contact_messages ORDER BY created_at DESC, id DESC LIMIT 500"
    ).fetchall()
    messages = [message_row_dict(r) for r in rows]
    total = db().execute("SELECT COUNT(*) c FROM contact_messages").fetchone()["c"]
    with_contact = db().execute(
        "SELECT COUNT(*) c FROM contact_messages WHERE email IS NOT NULL OR wechat IS NOT NULL"
    ).fetchone()["c"]
    return render_template(
        "admin_messages.html",
        user=g.user,
        auth_simple_nav=True,
        messages=messages,
        total=total,
        with_contact=with_contact,
    )


@app.get("/admin/messages.csv")
@admin_required
def admin_messages_csv():
    rows = db().execute(
        "SELECT * FROM contact_messages ORDER BY created_at DESC, id DESC"
    ).fetchall()
    output = io.StringIO()
    fields = ["id", "category", "subject", "message", "email", "wechat", "created_at"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        item = dict(row)
        writer.writerow({
            "id": item.get("id"),
            "category": item.get("category") or "",
            "subject": item.get("subject") or "",
            "message": item.get("message") or "",
            "email": item.get("email") or "",
            "wechat": item.get("wechat") or "",
            "created_at": item.get("created_at") or "",
        })
    data = "\ufeff" + output.getvalue()
    return Response(
        data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="expatus-contact-messages.csv"'},
    )


# ---------- Auth API ----------
@app.post("/api/auth/register/start")
def api_register_start():
    payload = request.get_json(silent=True) or {}
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password") or "")
    if not EMAIL_RE.match(email) or len(email) > 254:
        return jsonify(ok=False, error="请输入有效的邮箱地址。"), 400
    if len(password) < 8:
        return jsonify(ok=False, error="密码至少需要 8 位字符。"), 400
    existing = db().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if existing:
        return jsonify(ok=False, error="这个邮箱已经注册，直接登录即可。", action="login"), 409
    now = utcnow().isoformat()
    pw_hash = generate_password_hash(password)
    db().execute(
        "INSERT INTO pending_registrations(email,password_hash,created_at,updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash,updated_at=excluded.updated_at",
        (email, pw_hash, now, now),
    )
    db().commit()
    try:
        dev_code = send_verification_code(email, "register")
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 429
    except Exception:
        app.logger.exception("registration email failed")
        return jsonify(ok=False, error="验证码暂时无法发送，请稍后重试。"), 500
    session["pending_register_email"] = email
    return jsonify(ok=True, masked_email=masked_email(email), dev_code=dev_code)


@app.post("/api/auth/register/verify")
def api_register_verify():
    payload = request.get_json(silent=True) or {}
    email = session.get("pending_register_email")
    code = str(payload.get("code") or "").strip()
    if not email:
        return jsonify(ok=False, error="注册状态已失效，请重新开始。"), 400
    ok, error = verify_code(email, "register", code)
    if not ok:
        return jsonify(ok=False, error=error), 400
    pending = db().execute("SELECT * FROM pending_registrations WHERE email=?", (email,)).fetchone()
    if not pending:
        return jsonify(ok=False, error="注册信息已失效，请重新开始。"), 400
    now = utcnow().isoformat()
    cur = db().execute("INSERT INTO users(email,password_hash,verified_at,created_at) VALUES(?,?,?,?)", (email, pending["password_hash"], now, now))
    db().execute("DELETE FROM pending_registrations WHERE email=?", (email,))
    db().commit()
    target = safe_next(session.get("next_after_login") or payload.get("next") or "/")
    session.clear()
    session.permanent = True
    session["user_id"] = cur.lastrowid
    csrf_token()
    return jsonify(ok=True, redirect=target)


@app.post("/api/auth/login")
def api_login():
    payload = request.get_json(silent=True) or {}
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password") or "")
    row = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not row["password_hash"] or not check_password_hash(row["password_hash"], password):
        return jsonify(ok=False, error="邮箱或密码不正确。"), 401
    target = safe_next(payload.get("next") or session.get("next_after_login") or "/")
    session.clear()
    session.permanent = True
    session["user_id"] = row["id"]
    csrf_token()
    return jsonify(ok=True, redirect=target)


@app.post("/api/auth/forgot/start")
def api_forgot_start():
    payload = request.get_json(silent=True) or {}
    email = normalize_email(payload.get("email"))
    if not EMAIL_RE.match(email):
        return jsonify(ok=False, error="请输入有效的邮箱地址。"), 400
    row = db().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    dev_code = None
    if row:
        try:
            dev_code = send_verification_code(email, "reset")
        except ValueError as exc:
            return jsonify(ok=False, error=str(exc)), 429
        except Exception:
            app.logger.exception("reset email failed")
            return jsonify(ok=False, error="验证码暂时无法发送，请稍后重试。"), 500
    session["pending_reset_email"] = email
    session.pop("reset_verified", None)
    return jsonify(ok=True, masked_email=masked_email(email), dev_code=dev_code)


@app.post("/api/auth/forgot/verify")
def api_forgot_verify():
    payload = request.get_json(silent=True) or {}
    email = session.get("pending_reset_email")
    code = str(payload.get("code") or "").strip()
    if not email:
        return jsonify(ok=False, error="找回密码状态已失效，请重新开始。"), 400
    row = db().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if not row:
        return jsonify(ok=False, error="验证码不正确或已失效。"), 400
    ok, error = verify_code(email, "reset", code)
    if not ok:
        return jsonify(ok=False, error=error), 400
    session["reset_verified"] = True
    return jsonify(ok=True)


@app.post("/api/auth/reset")
def api_reset_password():
    payload = request.get_json(silent=True) or {}
    email = session.get("pending_reset_email")
    if not email or not session.get("reset_verified"):
        return jsonify(ok=False, error="验证状态已失效，请重新开始。"), 400
    password = str(payload.get("password") or "")
    if len(password) < 8:
        return jsonify(ok=False, error="密码至少需要 8 位字符。"), 400
    row = db().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if not row:
        return jsonify(ok=False, error="账户不存在。"), 400
    db().execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), row["id"]))
    db().commit()
    target = safe_next(payload.get("next") or "/")
    session.clear()
    session.permanent = True
    session["user_id"] = row["id"]
    csrf_token()
    return jsonify(ok=True, redirect=target)


@app.post("/api/auth/resend")
def api_auth_resend():
    payload = request.get_json(silent=True) or {}
    purpose = payload.get("purpose")
    if purpose == "register":
        email = session.get("pending_register_email")
    elif purpose == "reset":
        email = session.get("pending_reset_email")
    else:
        return jsonify(ok=False, error="无效操作。"), 400
    if not email:
        return jsonify(ok=False, error="当前验证状态已失效，请重新开始。"), 400
    if purpose == "reset" and not db().execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
        return jsonify(ok=True)
    try:
        dev_code = send_verification_code(email, purpose)
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 429
    except Exception:
        app.logger.exception("resend failed")
        return jsonify(ok=False, error="验证码暂时无法发送，请稍后重试。"), 500
    return jsonify(ok=True, dev_code=dev_code)


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


# ---------- Favorites API ----------
@app.post("/api/favorites/toggle")
@api_login_required
def api_favorite_toggle():
    payload = request.get_json(silent=True) or {}
    platform = str(payload.get("platform") or "").strip()
    if platform not in PLATFORM_BY_NAME:
        return jsonify(ok=False, error="未找到这个平台。"), 400
    row = db().execute("SELECT id FROM favorites WHERE user_id=? AND platform=?", (g.user["id"], platform)).fetchone()
    if row:
        db().execute("DELETE FROM favorites WHERE id=?", (row["id"],))
        favorite = False
    else:
        db().execute("INSERT INTO favorites(user_id,platform,created_at) VALUES(?,?,?)", (g.user["id"], platform, utcnow().isoformat()))
        favorite = True
    db().commit()
    return jsonify(ok=True, favorite=favorite)


# ---------- Progress API ----------
def owned_property(property_id):
    row = db().execute("SELECT * FROM properties WHERE id=? AND user_id=?", (property_id, g.user["id"])).fetchone()
    if not row:
        abort(404)
    return row


@app.post("/api/properties")
@api_login_required
def api_property_add():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    source = str(payload.get("source") or "").strip()
    url = str(payload.get("url") or "").strip()
    if not name or len(name) > 180:
        return jsonify(ok=False, error="请填写房源名称或地址。"), 400
    if len(source) > 120:
        return jsonify(ok=False, error="房源来源太长。"), 400
    if url and not valid_http_url(url):
        return jsonify(ok=False, error="房源链接需要以 http:// 或 https:// 开头。"), 400
    try:
        rent = parse_money(payload.get("rent"))
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    now = utcnow().isoformat()
    cur = db().execute(
        "INSERT INTO properties(user_id,name,source,rent,url,status,is_ended,created_at,updated_at) VALUES(?,?,?,?,?,'待处理',0,?,?)",
        (g.user["id"], name, source, rent, url or None, now, now),
    )
    db().commit()
    row = db().execute("SELECT * FROM properties WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(ok=True, property=property_dict(row))


@app.patch("/api/properties/<int:property_id>")
@api_login_required
def api_property_edit(property_id):
    owned_property(property_id)
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    source = str(payload.get("source") or "").strip()
    url = str(payload.get("url") or "").strip()
    if not name or len(name) > 180:
        return jsonify(ok=False, error="请填写房源名称或地址。"), 400
    if len(source) > 120:
        return jsonify(ok=False, error="房源来源太长。"), 400
    if url and not valid_http_url(url):
        return jsonify(ok=False, error="房源链接格式不正确。"), 400
    try:
        rent = parse_money(payload.get("rent"))
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    db().execute("UPDATE properties SET name=?,source=?,rent=?,url=?,updated_at=? WHERE id=?", (name, source, rent, url or None, utcnow().isoformat(), property_id))
    db().commit()
    return jsonify(ok=True)


@app.patch("/api/properties/<int:property_id>/status")
@api_login_required
def api_property_status(property_id):
    owned_property(property_id)
    payload = request.get_json(silent=True) or {}
    status = payload.get("status")
    if status not in STATUSES:
        return jsonify(ok=False, error="无效状态。"), 400
    db().execute("UPDATE properties SET status=?,is_ended=0,end_reason=NULL,ended_at=NULL,updated_at=? WHERE id=?", (status, utcnow().isoformat(), property_id))
    db().commit()
    return jsonify(ok=True)


@app.post("/api/properties/<int:property_id>/end")
@api_login_required
def api_property_end(property_id):
    owned_property(property_id)
    payload = request.get_json(silent=True) or {}
    reason = str(payload.get("reason") or "其他")
    if reason not in END_REASONS:
        reason = "其他"
    now = utcnow().isoformat()
    db().execute("UPDATE properties SET is_ended=1,end_reason=?,ended_at=?,updated_at=? WHERE id=?", (reason, now, now, property_id))
    db().commit()
    return jsonify(ok=True)


@app.post("/api/properties/<int:property_id>/restore")
@api_login_required
def api_property_restore(property_id):
    owned_property(property_id)
    db().execute("UPDATE properties SET status='待处理',is_ended=0,end_reason=NULL,ended_at=NULL,updated_at=? WHERE id=?", (utcnow().isoformat(), property_id))
    db().commit()
    return jsonify(ok=True)


@app.delete("/api/properties/<int:property_id>")
@api_login_required
def api_property_delete(property_id):
    owned_property(property_id)
    db().execute("DELETE FROM properties WHERE id=?", (property_id,))
    db().commit()
    return jsonify(ok=True)


# ---------- Rental dispute research form ----------
@app.post("/api/cases")
def api_case_submit():
    payload = request.get_json(silent=True) or {}
    description = str(payload.get("description") or "").strip()
    if len(description) < 10:
        return jsonify(ok=False, error="请至少用几句话简单描述发生了什么。"), 400
    if len(description) > 5000:
        return jsonify(ok=False, error="描述过长，请压缩到 5000 字以内。"), 400
    email = normalize_email(payload.get("email")) if payload.get("email") else ""
    if email and not EMAIL_RE.match(email):
        return jsonify(ok=False, error="邮箱格式不正确。"), 400
    issues = payload.get("issues") or []
    if not isinstance(issues, list):
        issues = []
    issues = [str(x)[:60] for x in issues[:12]]
    try:
        base_rent = parse_money(payload.get("base_rent"))
        deposit_amount = parse_money(payload.get("deposit"))
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400

    # Lightweight per-session abuse guard: at most 5 submissions per hour.
    recent = session.get("case_submit_times", [])
    cutoff = utcnow().timestamp() - 3600
    recent = [t for t in recent if t >= cutoff]
    if len(recent) >= 5:
        return jsonify(ok=False, error="提交次数较多，请稍后再试。"), 429

    db().execute(
        """INSERT INTO case_submissions(user_id,city,contract_date,rental_ended,moveout_date,base_rent,deposit,issues_json,checkin_report,deduction_spec,description,email,wechat,contact_ok,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            g.user["id"] if g.user else None,
            str(payload.get("city") or "").strip()[:120], str(payload.get("contract_date") or "")[:20], str(payload.get("rental_ended") or "")[:30],
            str(payload.get("moveout_date") or "")[:20], base_rent, deposit_amount, json.dumps(issues, ensure_ascii=False),
            str(payload.get("checkin_report") or "")[:30], str(payload.get("deduction_spec") or "")[:30], description,
            email[:254] or None, str(payload.get("wechat") or "").strip()[:120] or None, 1 if payload.get("contact_ok") else 0, utcnow().isoformat(),
        ),
    )
    db().commit()
    recent.append(utcnow().timestamp())
    session["case_submit_times"] = recent
    return jsonify(ok=True)



# ---------- Contact message form ----------
@app.post("/api/contact")
def api_contact_submit():
    payload = request.get_json(silent=True) or {}
    category = str(payload.get("category") or "其他").strip()[:40]
    allowed_categories = {"网站建议", "找房资源补充", "租房问题", "合作", "其他"}
    if category not in allowed_categories:
        category = "其他"

    subject = str(payload.get("subject") or "").strip()[:120]
    message = str(payload.get("message") or "").strip()
    if len(message) < 5:
        return jsonify(ok=False, error="请至少写几句话告诉我们你的留言。"), 400
    if len(message) > 4000:
        return jsonify(ok=False, error="留言过长，请压缩到 4000 字以内。"), 400

    email = normalize_email(payload.get("email")) if payload.get("email") else ""
    if email and not EMAIL_RE.match(email):
        return jsonify(ok=False, error="邮箱格式不正确。"), 400
    wechat = str(payload.get("wechat") or "").strip()[:120]

    recent = session.get("contact_submit_times", [])
    cutoff = utcnow().timestamp() - 3600
    recent = [t for t in recent if t >= cutoff]
    if len(recent) >= 5:
        return jsonify(ok=False, error="留言次数较多，请稍后再试。"), 429

    db().execute(
        """INSERT INTO contact_messages(user_id,category,subject,message,email,wechat,created_at)
           VALUES(?,?,?,?,?,?,?)""",
        (
            g.user["id"] if g.user else None,
            category,
            subject or None,
            message,
            email[:254] or None,
            wechat or None,
            utcnow().isoformat(),
        ),
    )
    db().commit()
    recent.append(utcnow().timestamp())
    session["contact_submit_times"] = recent
    return jsonify(ok=True)


# ---------- Static / compatibility / SEO-preserving aliases ----------
@app.get("/favicon-32x32.png")
def favicon_png():
    return send_from_directory(BASE_DIR / "static", "favicon-32x32.png")


@app.get("/apple-touch-icon.png")
def apple_touch_icon():
    return send_from_directory(BASE_DIR / "static", "apple-touch-icon.png")


@app.get("/og-image.png")
def og_image():
    return send_from_directory(BASE_DIR / "static", "og-image.png")


@app.get("/downloads/<path:name>")
def download_file(name):
    allowed = {"contract-checklist.pdf", "move-in-checklist.pdf"}
    if name not in allowed:
        abort(404)
    return send_from_directory(BASE_DIR / "static" / "downloads", name, as_attachment=True)


@app.get("/index.html")
def index_alias():
    return redirect(url_for("home"), code=301)


@app.get("/account-login.html")
def auth_alias():
    return redirect(url_for("auth"), code=301)


@app.get("/my-rental-progress.html")
def progress_alias():
    return redirect(url_for("progress"), code=301)


@app.get("/leiden-rental-guide.html")
@app.get("/leiden-rental-guide/")
def leiden_alias():
    return redirect(url_for("leiden"), code=301)


@app.get("/deposit-return-netherlands/")
def deposit_alias():
    return redirect(url_for("deposit"), code=301)


@app.errorhandler(404)
def not_found(_exc):
    return render_template("404.html", user=g.user), 404


if __name__ == "__main__":
    ensure_db_initialized()
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8000")), debug=os.getenv("FLASK_DEBUG", "1") == "1")
