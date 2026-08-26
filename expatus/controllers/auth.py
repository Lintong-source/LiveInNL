"""Account registration, verified login and password recovery endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from expatus.repositories import users
from expatus.services import audit, email_codes
from expatus.services.security import check_rate_limit, csrf_token
from expatus.services.validation import masked_email, normalize_email, safe_next, valid_email


blueprint = Blueprint("auth", __name__)


def _login_session(user_id: int) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    csrf_token()


@blueprint.post("/api/auth/register/start")
def register_start():
    payload = request.get_json(silent=True) or {}
    email = normalize_email(payload.get("email"))
    password = str(payload.get("password") or "")
    if not valid_email(email):
        return jsonify(ok=False, error="请输入有效的邮箱地址。"), 400
    if len(password) < 8 or len(password) > 256:
        return jsonify(ok=False, error="密码需要为 8 至 256 位字符。"), 400
    if payload.get("privacy_acknowledged") is not True:
        return jsonify(ok=False, error="请先阅读并确认隐私声明。"), 400
    if payload.get("website"):
        return jsonify(ok=True, masked_email=masked_email(email))
    if not check_rate_limit("register", maximum=8, seconds=3600, discriminator=email):
        return jsonify(ok=False, error="注册请求过于频繁，请稍后再试。"), 429
    if users.find_by_email(email):
        return jsonify(ok=False, error="这个邮箱已经注册，直接登录即可。", action="login"), 409

    settings = current_app.config["EXPATUS_SETTINGS"]
    users.save_pending(email, generate_password_hash(password), policy_version=settings.privacy_policy_version)
    try:
        dev_code = email_codes.send(email, "register")
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 429
    except Exception:
        current_app.logger.exception("Unable to send registration verification email")
        return jsonify(ok=False, error="验证码暂时无法发送，请稍后重试。"), 500
    session["pending_register_email"] = email
    audit.record("register_started", subject=masked_email(email))
    return jsonify(ok=True, masked_email=masked_email(email), dev_code=dev_code)


@blueprint.post("/api/auth/register/verify")
def register_verify():
    payload = request.get_json(silent=True) or {}
    email = session.get("pending_register_email")
    if not email:
        return jsonify(ok=False, error="注册状态已失效，请重新开始。"), 400
    accepted, error = email_codes.verify(email, "register", str(payload.get("code") or "").strip())
    if not accepted:
        return jsonify(ok=False, error=error), 400
    try:
        user_id = users.activate_pending(email)
    except ValueError as exception:
        return jsonify(ok=False, error=str(exception)), 400
    target = safe_next(session.get("next_after_login") or payload.get("next") or "/workspace/strategy")
    _login_session(user_id)
    audit.record("register_completed", user_id=user_id, subject=masked_email(email))
    return jsonify(ok=True, redirect=target)


@blueprint.post("/api/auth/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = normalize_email(payload.get("email"))
    if not check_rate_limit("login", maximum=12, seconds=900, discriminator=email):
        return jsonify(ok=False, error="尝试次数过多，请稍后再试。"), 429
    row = users.find_by_email(email)
    if not row or not row["password_hash"] or not check_password_hash(
        row["password_hash"], str(payload.get("password") or "")
    ):
        audit.record("login_failed", outcome="denied", subject=masked_email(email) if valid_email(email) else "invalid")
        return jsonify(ok=False, error="邮箱或密码不正确。"), 401
    target = safe_next(payload.get("next") or session.get("next_after_login") or "/workspace/strategy")
    _login_session(row["id"])
    users.set_last_login(row["id"])
    audit.record("login_success", user_id=row["id"])
    # Accounts created before the privacy notice existed must review it once.
    if not row["privacy_acknowledged_at"]:
        target = url_for("pages.privacy", acknowledge=1, next=target)
    return jsonify(ok=True, redirect=target)


@blueprint.post("/api/auth/forgot/start")
def forgot_start():
    payload = request.get_json(silent=True) or {}
    email = normalize_email(payload.get("email"))
    if not valid_email(email):
        return jsonify(ok=False, error="请输入有效的邮箱地址。"), 400
    if not check_rate_limit("password_reset", maximum=5, seconds=3600, discriminator=email):
        return jsonify(ok=False, error="请求次数过多，请稍后再试。"), 429
    dev_code = None
    if users.find_by_email(email):
        try:
            dev_code = email_codes.send(email, "reset")
        except ValueError as error:
            return jsonify(ok=False, error=str(error)), 429
        except Exception:
            current_app.logger.exception("Unable to send password-reset verification email")
            return jsonify(ok=False, error="验证码暂时无法发送，请稍后重试。"), 500
    session["pending_reset_email"] = email
    session.pop("reset_verified", None)
    return jsonify(ok=True, masked_email=masked_email(email), dev_code=dev_code)


@blueprint.post("/api/auth/forgot/verify")
def forgot_verify():
    payload = request.get_json(silent=True) or {}
    email = session.get("pending_reset_email")
    if not email or not users.find_by_email(email):
        return jsonify(ok=False, error="验证码不正确或已失效。"), 400
    accepted, error = email_codes.verify(email, "reset", str(payload.get("code") or "").strip())
    if not accepted:
        return jsonify(ok=False, error=error), 400
    session["reset_verified"] = True
    return jsonify(ok=True)


@blueprint.post("/api/auth/reset")
def reset_password():
    payload = request.get_json(silent=True) or {}
    email = session.get("pending_reset_email")
    if not email or not session.get("reset_verified"):
        return jsonify(ok=False, error="验证状态已失效，请重新开始。"), 400
    password = str(payload.get("password") or "")
    if len(password) < 8 or len(password) > 256:
        return jsonify(ok=False, error="密码需要为 8 至 256 位字符。"), 400
    row = users.find_by_email(email)
    if not row:
        return jsonify(ok=False, error="账户不存在。"), 400
    users.set_password(row["id"], generate_password_hash(password))
    target = safe_next(payload.get("next") or "/workspace/strategy")
    _login_session(row["id"])
    audit.record("password_reset", user_id=row["id"])
    return jsonify(ok=True, redirect=target)


@blueprint.post("/api/auth/resend")
def resend():
    payload = request.get_json(silent=True) or {}
    purpose = payload.get("purpose")
    if purpose not in {"register", "reset"}:
        return jsonify(ok=False, error="无效操作。"), 400
    key = "pending_register_email" if purpose == "register" else "pending_reset_email"
    email = session.get(key)
    if not email:
        return jsonify(ok=False, error="当前验证状态已失效，请重新开始。"), 400
    if purpose == "reset" and not users.find_by_email(email):
        return jsonify(ok=True)
    try:
        dev_code = email_codes.send(email, purpose)
    except ValueError as error:
        return jsonify(ok=False, error=str(error)), 429
    except Exception:
        current_app.logger.exception("Unable to resend verification email")
        return jsonify(ok=False, error="验证码暂时无法发送，请稍后重试。"), 500
    return jsonify(ok=True, dev_code=dev_code)


@blueprint.post("/logout")
def logout():
    if g.user:
        audit.record("logout")
    session.clear()
    return redirect(url_for("pages.home"))
