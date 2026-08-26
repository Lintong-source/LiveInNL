"""Collect and package a signed-in user's readable, portable personal data."""

from __future__ import annotations

import csv
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

from expatus.database import get_db
from expatus.repositories import favorites, properties
from expatus.services.clock import utcnow


def collect(user) -> dict:
    """Every query is scoped by the verified session user, never by client input."""
    user_id = user["id"]
    return {
        "account": {
            "email": user["email"],
            "created_at": user["created_at"],
            "verified_at": user["verified_at"],
            "privacy_acknowledged_at": user["privacy_acknowledged_at"],
            "privacy_policy_version": user["privacy_policy_version"],
        },
        "rental_properties": [properties.serialize(row) for row in properties.list_for_user(user_id)],
        "favorites": favorites.names_for_user(user_id),
        "strategy_generations": _rows(
            "SELECT identity_type,city,move_date,home_type,budget,income_type,"
            "student_registration,university_housing,area_flexibility,result_summary,"
            "engine_version,result_json,created_at "
            "FROM strategy_generations WHERE user_id=? ORDER BY created_at DESC",
            user_id,
        ),
        "contact_messages": _rows(
            "SELECT category,subject,message,email,wechat,created_at "
            "FROM contact_messages WHERE user_id=? ORDER BY created_at DESC",
            user_id,
        ),
        "rental_case_submissions": _rows(
            "SELECT city,contract_date,rental_ended,moveout_date,base_rent,deposit,"
            "issues_json,checkin_report,deduction_spec,description,email,wechat,contact_ok,created_at "
            "FROM case_submissions WHERE user_id=? ORDER BY created_at DESC",
            user_id,
        ),
        "account_activity": _rows(
            "SELECT event_type,outcome,created_at FROM audit_events "
            "WHERE user_id=? ORDER BY created_at DESC LIMIT 300",
            user_id,
        ),
    }


def _rows(sql: str, user_id: int) -> list[dict]:
    return [dict(row) for row in get_db().execute(sql, (user_id,)).fetchall()]


TABLES = (
    (
        "01-房源进度.csv",
        "rental_properties",
        (("name", "房源"), ("source", "来源"), ("rent", "月租"), ("url", "链接"),
         ("status", "当前状态"), ("is_ended", "已结束"), ("reason", "结束原因")),
    ),
    (
        "02-收藏平台.csv",
        "favorites",
        (("platform", "平台"),),
    ),
    (
        "03-找房策略.csv",
        "strategy_generations",
        (("identity_type", "身份"), ("city", "城市"), ("move_date", "入住日期"),
         ("home_type", "房型"), ("budget", "预算"), ("income_type", "收入类型"),
         ("student_registration", "学生住房注册"), ("university_housing", "学校住房"),
         ("area_flexibility", "周边城市"), ("result_summary", "策略摘要"),
         ("engine_version", "策略引擎版本"),
         ("created_at", "生成时间")),
    ),
    (
        "04-联系留言.csv",
        "contact_messages",
        (("category", "类别"), ("subject", "主题"), ("message", "留言"),
         ("email", "邮箱"), ("wechat", "微信"), ("created_at", "提交时间")),
    ),
    (
        "05-租房问题.csv",
        "rental_case_submissions",
        (("city", "城市"), ("contract_date", "合同日期"), ("rental_ended", "租约结束"),
         ("moveout_date", "搬出日期"), ("base_rent", "月租"), ("deposit", "押金"),
         ("issues_json", "问题类别"), ("description", "问题描述"),
         ("email", "邮箱"), ("wechat", "微信"), ("contact_ok", "允许联系"),
         ("created_at", "提交时间")),
    ),
    (
        "06-账户活动.csv",
        "account_activity",
        (("event_type", "事件"), ("outcome", "结果"), ("created_at", "时间")),
    ),
)


def _safe_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    text = str(value)
    # Prevent a saved title/message from becoming a formula in Excel or Sheets.
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def _csv_bytes(rows, columns) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([label for _, label in columns])
    for row in rows:
        if isinstance(row, str):
            row = {"platform": row}
        writer.writerow([_safe_cell(row.get(field)) for field, _ in columns])
    return output.getvalue().encode("utf-8-sig")


def build_archive(data: dict) -> bytes:
    """Offer readable Chinese-labelled CSV files plus a portable JSON copy."""
    output = io.BytesIO()
    account = data["account"]
    overview = "\n".join(
        (
            "Expatus 个人数据导出",
            "",
            f"账户邮箱：{account['email']}",
            f"注册时间：{account['created_at']}",
            f"邮箱验证时间：{account['verified_at']}",
            f"隐私声明确认时间：{account['privacy_acknowledged_at'] or '暂无'}",
            f"隐私声明版本：{account['privacy_policy_version'] or '暂无'}",
            f"导出时间：{utcnow().isoformat()}",
            "",
            "CSV 文件可使用 Excel、Numbers 或电子表格软件直接打开。",
            "完整数据.json 供数据迁移或技术用途使用，可按需忽略。",
            "此压缩包只包含当前登录账户的数据，不包含密码或验证码。",
        )
    )
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("00-账户说明.txt", overview.encode("utf-8-sig"))
        for filename, key, columns in TABLES:
            archive.writestr(filename, _csv_bytes(data[key], columns))
        archive.writestr(
            "07-完整数据.json", json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        )
    return output.getvalue()
