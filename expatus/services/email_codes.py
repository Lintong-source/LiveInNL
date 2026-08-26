"""Generate, throttle, email and verify one-time authentication codes."""

from __future__ import annotations

import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import current_app

from expatus.database import get_db
from expatus.services.clock import utcnow


def _hash_code(email: str, purpose: str, code: str) -> str:
    payload = f"{current_app.secret_key}:{purpose}:{email}:{code}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def send(email: str, purpose: str):
    now = utcnow()
    latest = get_db().execute(
        "SELECT created_at FROM verification_codes WHERE email=? AND purpose=? "
        "ORDER BY id DESC LIMIT 1",
        (email, purpose),
    ).fetchone()
    if latest and now - datetime.fromisoformat(latest["created_at"]) < timedelta(seconds=60):
        raise ValueError("请等待约 60 秒后再重新发送验证码。")
    recent = get_db().execute(
        "SELECT COUNT(*) AS total FROM verification_codes WHERE email=? AND purpose=? AND created_at>=?",
        (email, purpose, (now - timedelta(hours=1)).isoformat()),
    ).fetchone()["total"]
    if recent >= 5:
        raise ValueError("这个邮箱一小时内发送次数过多，请稍后再试。")

    settings = current_app.config["EXPATUS_SETTINGS"]
    code = "123456" if settings.demo_mode and email == "demo@expatus.test" else f"{secrets.randbelow(1_000_000):06d}"
    get_db().execute(
        "UPDATE verification_codes SET used_at=? WHERE email=? AND purpose=? AND used_at IS NULL",
        (now.isoformat(), email, purpose),
    )
    get_db().execute(
        "INSERT INTO verification_codes(email,purpose,code_hash,expires_at,created_at) VALUES(?,?,?,?,?)",
        (email, purpose, _hash_code(email, purpose, code), (now + timedelta(minutes=10)).isoformat(), now.isoformat()),
    )
    get_db().commit()

    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        if settings.is_production:
            raise RuntimeError("Production requires SMTP_HOST before verification emails can be sent.")
        current_app.logger.info("Local %s verification code for %s: %s", purpose, email, code)
        return code if settings.show_verification_code else None

    username = os.getenv("SMTP_USERNAME", "")
    message = EmailMessage()
    message["Subject"] = "Expatus 邮箱验证码" if purpose == "register" else "Expatus 重置密码验证码"
    message["From"] = os.getenv("SMTP_FROM", username)
    message["To"] = email
    message.set_content(
        f"你的 Expatus 验证码是：{code}\n\n验证码 10 分钟内有效。"
        "如果不是你本人操作，请忽略这封邮件。"
    )
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as smtp:
        if os.getenv("SMTP_STARTTLS", "1") == "1":
            smtp.starttls()
        if username:
            smtp.login(username, os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(message)
    return None


def verify(email: str, purpose: str, code: str):
    row = get_db().execute(
        "SELECT * FROM verification_codes WHERE email=? AND purpose=? AND used_at IS NULL "
        "ORDER BY id DESC LIMIT 1",
        (email, purpose),
    ).fetchone()
    if row is None:
        return False, "验证码不存在或已失效，请重新获取。"
    if row["attempts"] >= 5:
        return False, "验证码错误次数过多，请重新获取。"
    if datetime.fromisoformat(row["expires_at"]) < utcnow():
        return False, "验证码已过期，请重新获取。"
    if not (len(code) == 6 and code.isdigit()) or not secrets.compare_digest(
        row["code_hash"], _hash_code(email, purpose, code)
    ):
        get_db().execute("UPDATE verification_codes SET attempts=attempts+1 WHERE id=?", (row["id"],))
        get_db().commit()
        return False, "验证码不正确，请重新输入。"
    get_db().execute("UPDATE verification_codes SET used_at=? WHERE id=?", (utcnow().isoformat(), row["id"]))
    get_db().commit()
    return True, None
