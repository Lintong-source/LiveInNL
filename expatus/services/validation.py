"""Input validation shared by controllers and business services."""

from __future__ import annotations

import re
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
TAG_RE = re.compile(r"<\s*/?\s*(script|iframe|object|embed|form|svg)\b", re.I)
URL_RE = re.compile(r"(?:https?://|www\.)", re.I)
CJK_RE = re.compile(r"[\u3400-\u9fff]")
LATIN_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]{2,}")
REPEATED_FRAGMENT_RE = re.compile(r"(.{1,5})\1{2,}", re.I)
WECHAT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{5,19}$")
KEYBOARD_FRAGMENTS = ("qwerty", "asdf", "zxcv", "qweqwe", "asdasd", "zxczxc", "123123")
SHORT_RENTAL_TERMS = {"bug", "bsn", "brp", "duwo", "funda", "room", "ssh", "wws", "xior"}


def normalize_email(value) -> str:
    return str(value or "").strip().lower()


def valid_email(value: str) -> bool:
    return len(value) <= 254 and bool(EMAIL_RE.fullmatch(value))


def masked_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return f"{local[:3]}{'***' if len(local) > 3 else ''}@{domain}"


def safe_text(value, maximum: int, *, multiline: bool = False) -> str:
    text = str(value or "").strip()
    if CONTROL_RE.search(text):
        raise ValueError("提交内容包含不允许的控制字符。")
    if not multiline and ("\r" in text or "\n" in text):
        raise ValueError("输入内容格式不正确。")
    if len(text) > maximum:
        raise ValueError(f"输入内容不能超过 {maximum} 个字符。")
    if TAG_RE.search(text):
        raise ValueError("提交内容不能包含脚本或嵌入标签。")
    return text


def enforce_reasonable_links(value: str, maximum: int = 3) -> None:
    if len(URL_RE.findall(value)) > maximum:
        raise ValueError("链接数量过多，请删除无关链接后重试。")


def _keyboard_or_repeated(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", value.lower())
    if len(normalized) < 5:
        return False
    if any(fragment in normalized for fragment in KEYBOARD_FRAGMENTS):
        return True
    return bool(REPEATED_FRAGMENT_RE.search(normalized))


def ensure_meaningful_message(value: str, *, minimum: int = 8) -> None:
    """Reject keyboard noise while accepting normal Chinese and English messages."""
    compact = re.sub(r"\s+", "", value)
    if len(compact) < minimum:
        raise ValueError("请补充清楚你遇到的问题或建议，至少填写 8 个字。")
    chinese = CJK_RE.findall(value)
    words = LATIN_WORD_RE.findall(value)
    if len(chinese) >= 4:
        if len(set(chinese)) < 3 or _keyboard_or_repeated("".join(chinese)):
            raise ValueError("留言内容存在重复或无意义字符，请描述具体问题。")
        return
    if len(words) < 3 or sum(map(len, words)) < 10:
        raise ValueError("请填写完整的留言内容，不要只输入随机字母或字符。")
    if _keyboard_or_repeated(compact) or len(set(compact.lower())) < 5:
        raise ValueError("留言内容存在重复或键盘随机输入，请重新填写。")


def ensure_meaningful_subject(value: str) -> None:
    if not value:
        return
    if CJK_RE.search(value):
        return
    words = LATIN_WORD_RE.findall(value)
    letters = "".join(words).lower()
    if letters in SHORT_RENTAL_TERMS:
        return
    if _keyboard_or_repeated(value) or not words:
        raise ValueError("留言主题看起来像随机输入，请修改或留空。")
    if len(words) == 1:
        vowels = sum(character in "aeiouy" for character in letters)
        if len(letters) < 6 or vowels < 2 or re.search(r"[bcdfghjklmnpqrstvwxz]{4,}", letters):
            raise ValueError("留言主题请写明具体事项；不需要主题时可以留空。")


def ensure_reasonable_contact(email: str, wechat: str) -> None:
    if email:
        local = email.partition("@")[0]
        if _keyboard_or_repeated(local):
            raise ValueError("邮箱看起来像随机输入，请填写真实邮箱或留空。")
    if wechat:
        if not WECHAT_RE.fullmatch(wechat) or _keyboard_or_repeated(wechat):
            raise ValueError("微信号格式不正确或像随机输入；不需要联系时请留空。")


def parse_money(value):
    if value in (None, ""):
        return None
    try:
        amount = float(str(value).replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise ValueError("金额格式不正确。") from exc
    if amount < 0 or amount > 1_000_000:
        raise ValueError("金额格式不正确。")
    return amount


def valid_http_url(value: str) -> bool:
    if not value:
        return True
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def safe_next(value: str | None) -> str:
    if not value:
        return "/"
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/") or value.startswith("//"):
        return "/"
    return value
