"""Versioned, deterministic backend engine for personalized rental strategies.

The browser renders this module's structured result. It must not reproduce or
override business rules. Keeping the engine pure makes every decision testable.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


ENGINE_VERSION = "strategy-v2-backend-2026-08-26"
AMSTERDAM = ZoneInfo("Europe/Amsterdam")

IDENTITY_LABELS = {
    "master": "硕士 / 国际学生",
    "bachelor": "本科生",
    "phd": "PhD / 访问学者",
    "worker": "在职人士",
    "family": "情侣 / 家庭",
}
HOME_LABELS = {"room": "Room / 合租单间", "studio": "Studio", "apartment": "Apartment / 整租"}
INCOME_LABELS = {"none": "暂无稳定荷兰收入", "salary": "固定工资收入", "stipend": "PhD / stipend / scholarship"}
PHASES = (
    {"name": "提前布局", "range": "> 90 天"},
    {"name": "主动找房", "range": "46–90 天"},
    {"name": "扩大覆盖", "range": "15–45 天"},
    {"name": "紧急落地", "range": "≤ 14 天"},
)
EFFORT_COLORS = {
    "student": "#1e5631",
    "commercial": "#3d8b7a",
    "operator": "#c4943a",
    "social": "#5b7fa3",
    "review": "#8b6553",
}


def _today() -> date:
    return datetime.now(AMSTERDAM).date()


def _days_to(move_date: str, today: date | None) -> int:
    return max(0, (date.fromisoformat(move_date) - (today or _today())).days)


def _phase_index(days: int) -> int:
    if days > 90:
        return 0
    if days > 45:
        return 1
    if days > 14:
        return 2
    return 3


def _is_student(profile: dict) -> bool:
    return profile["identity"] in {"master", "bachelor", "phd"}


def _status(days: int, progress: dict) -> dict:
    phase = _phase_index(days)
    if progress["confirmed"]:
        return {"icon": "✓", "title": "已经出现确定住房：策略进入收尾阶段", "description": "你已经记录了确定住房。渠道搜索可以逐步降频，把注意力转向合同、入住与后续事项；正式签约完成前仍保留必要跟进。"}
    if progress["applications"] >= 15 and progress["viewings"] == 0:
        return {"icon": "!", "title": "申请有量但转化偏低：先检查适配度，不要只加投递量", "description": f"当前记录中已有 {progress['applications']} 套房源进入联系或申请阶段，但还没有 Viewing。系统会降低无差别加量建议，优先检查收入条件、学生限制、材料完整度和渠道覆盖。"}
    if progress["viewings"] >= 1:
        return {"icon": "→", "title": "已经产生有效反馈：保持主线，不急着大幅换策略", "description": f"目前已经记录 {progress['viewings']} 个 Viewing，说明至少部分渠道正在工作。继续保持有效线路，同时跟进正在推进的房源。"}
    choices = (
        {"icon": "◎", "title": "提前布局期：先启动时间会增值的渠道", "description": "现在优先完成需要注册时间、资格或排队的线路，同时配置之后要使用的主动渠道。"},
        {"icon": "→", "title": "主动找房期：等待线保留，主动申请成为日常", "description": "继续保留被动渠道，同时把每日精力逐步转向商业平台、运营商和与你房型匹配的主动渠道。"},
        {"icon": "!", "title": "扩大覆盖期：不要只靠原来的主要渠道", "description": "入住日期正在接近。如果还没有明显进展，应提高周边城市、合租与社群渠道权重，并准备临时落地方案。"},
        {"icon": "⚑", "title": "紧急落地期：长期找房与落地方案并行", "description": "长期住房继续找，同时确保抵达后有合法、安全的临时住宿方案，避免因时间压力接受高风险房源。"},
    )
    return choices[phase]


def _platforms(kind: str, profile: dict, phase: int) -> list[dict]:
    city = profile["city"]
    if kind == "student":
        registered = profile["studentReg"] == "registered"
        return [
            {"name": "ROOM.nl", "state": "已注册 · 后台运行" if registered else "今天完成注册", "tone": "wait" if registered else "do", "note": "确认官方提醒即可，不需要把每天主要时间花在刷新排名。" if registered else "先确认目标城市是否属于对应体系；如果符合条件，注册时间不要再往后拖。", "label": "查看注册体系", "url": "https://www.room.nl/"},
            {"name": "DUWO / 当地学生住房机构", "state": "确认城市覆盖", "tone": "warn", "note": "机构与注册入口不是一回事。先查目标城市对应机构，再按官方入口行动。", "label": "查看城市指南", "url": "/city/den-haag" if city == "Den Haag" else "/city/leiden"},
            {"name": "学生住房邮件提醒", "state": "检查已开启" if registered else "注册后开启", "tone": "watch", "note": "真正出现可申请房源时再迅速行动，比无变化时频繁刷新更有效。", "label": "检查提醒", "url": "https://www.room.nl/"},
        ]
    if kind == "school":
        waiting = profile["universityHousing"] == "waiting"
        city_url = "/city/den-haag" if city == "Den Haag" else "/city/leiden"
        return [
            {"name": "University Housing", "state": "已申请 / 等待" if waiting else "今天确认资格", "tone": "wait" if waiting else "do", "note": "学校合作库存通常需要学校先给予资格或进入等待名单。", "label": "查看学校 Housing 页面", "url": city_url},
            {"name": "International Office", "state": "必要时联系", "tone": "warn", "note": "如果官网没有写清资格、批次或等待名单，直接向学校确认。", "label": "准备询问", "url": city_url},
        ]
    if kind == "commercial":
        return [
            {"name": "Pararius", "state": "今天设置提醒" if phase == 0 else "每日查看", "tone": "do" if phase == 0 else "watch", "note": "先看 student / income requirement，再申请；不要为了数量投明显不符合条件的房。", "label": "打开平台", "url": "https://www.pararius.com/"},
            {"name": "Funda", "state": "保存搜索" if phase == 0 else "保持关注", "tone": "watch", "note": "租房库存可能没有 Pararius 多，适合作为独立入口和补充提醒。", "label": "打开平台", "url": "https://www.funda.nl/"},
            {"name": "Huurwoningen.nl", "state": "补充搜索", "tone": "wait", "note": "作为额外房源入口；申请前仍需确认实际出租方与收费规则。", "label": "加入渠道", "url": "https://www.huurwoningen.nl/"},
        ]
    if kind == "operator":
        return [
            {"name": "Holland2Stay", "state": "建立账号 / 看库存", "tone": "watch", "note": "房源释放不连续。没有库存时无需反复空刷，有新房时再快速处理。", "label": "加入关注", "url": "https://holland2stay.com/"},
            {"name": "MVGM / ikwilhuren.nu", "state": "保存条件", "tone": "wait", "note": "运营商直租与综合平台不同，值得单独建立账号和提醒。", "label": "加入关注", "url": "https://ikwilhuren.nu/"},
            {"name": "Vesteda", "state": "按城市核对库存", "tone": "wait", "note": "根据目标区域和收入条件决定是否长期保留。", "label": "加入关注", "url": "https://www.vesteda.com/"},
        ]
    if kind == "social":
        active = profile["homeType"] == "room" or phase >= 2
        return [
            {"name": "Kamernet", "state": "加强主动联系" if active else "先建立账号", "tone": "watch" if active else "wait", "note": "找 Room 时更重要。写好个人介绍，优先联系真正匹配的房源。", "label": "加入渠道", "url": "https://kamernet.nl/"},
            {"name": "Facebook Housing Groups", "state": "提高频率" if phase >= 2 else "先加入观察", "tone": "warn" if phase >= 2 else "wait", "note": "信息变化快但真实性差异大；不要因为临近入住就降低核验标准。", "label": "加入信息源", "url": "/rental-channels"},
            {"name": "微信 / 小红书租房信息", "state": "后期加强" if phase >= 2 else "目前补充", "tone": "warn" if phase >= 2 else "wait", "note": "越临近入住越可能成为救急线，但必须核实合同、实际出租权与地址登记。", "label": "加入信息源", "url": "/rental-channels"},
        ]
    return [{"name": "周边城市 / 通勤圈", "state": "今天扩大搜索", "tone": "do", "note": f"从 {city} 向可接受通勤范围扩展，而不是继续在同一房源池里重复刷新。", "label": "调整区域", "url": "/city/leiden" if city == "Den Haag" else "/city/den-haag"}]


def _channels(profile: dict, progress: dict, days: int) -> list[dict]:
    phase = _phase_index(days)
    student = _is_student(profile)
    room = profile["homeType"] == "room"
    stuck = progress["applications"] >= 15 and progress["viewings"] == 0
    confirmed = bool(progress["confirmed"])
    result = []

    def add(kind, name, subtitle, stars, state, tone, action, effort, why, adjust):
        if confirmed:
            state, tone, action, effort = "可暂停", "passive", "保留必要通知，停止新增申请", "很低"
        elif stuck and kind in {"commercial", "social"}:
            state, tone, action = "先检查转化", "urgent", "暂停无差别加量，检查门槛、材料与申请时机"
        elif progress["viewings"] >= 1 and progress["mainChannel"] == kind:
            stars, state, tone = 5, "当前有效", "daily"
            action = "保持这条已产生 Viewing 的主线，重点跟进正在推进的房源"
        result.append({"kind": kind, "name": name, "subtitle": subtitle, "stars": stars, "state": state, "tone": tone, "action": action, "effort": effort, "why": why, "adjust": adjust, "platforms": _platforms(kind, profile, phase)})

    if student:
        registered = profile["studentReg"] == "registered"
        add("student", "学生住房注册体系", f"{profile['city']} · ROOM / 当地 student housing", 5, "后台运行" if registered else "立即启动", "passive" if registered else "urgent", "保持注册有效，确认官方提醒已开启" if registered else "今天确认当地体系并完成注册", "很低" if registered else "一次性", "价值来自资格、注册时间或分配规则，不来自每天高频刷新。", "出现 Direct Offer、lottery 或可申请房源时立即行动。")
        waiting = profile["universityHousing"] == "waiting"
        add("school", "学校合作住房", "University Housing / institution allocation", 5 if profile["identity"] == "phd" else 4, "排队 / 等待" if waiting else "先确认资格", "passive" if waiting else "urgent", "继续等待，同时不要停掉其他渠道" if waiting else "联系学校确认资格、窗口或等待名单", "低", "这类房源取决于学校资格与库存，个人可主动推进空间有限。", "如果排队长期无变化，不应停止商业市场和 Room 渠道。")

    commercial_stars = 5 if profile["income"] == "salary" else (3 if profile["homeType"] == "apartment" else 4)
    add("commercial", "Pararius / Funda", "综合租房平台 · commercial rental", commercial_stars, "配置提醒" if phase == 0 else "每日主战", "passive" if phase == 0 else "daily", "保存搜索条件并熟悉规则" if phase == 0 else "每天查看新房源，只投符合身份和收入门槛的申请", "低" if phase == 0 else "高", "它们能持续产生新房源和反馈，但不是所有房源都值得申请。", "回复率低时先检查资格和材料，不要只增加投递量。")
    add("operator", "住房运营商官网", "housing provider · direct rental", 4, "加强关注" if phase >= 2 else "配置并等待", "daily" if phase >= 2 else "passive", "建立账号、保存条件并开启提醒；有库存时尽快申请", "中" if phase >= 2 else "低", "运营商库存不连续，更适合配置好后等待机会。", "临近入住时提高检查频率。")
    social_early = room or profile["budget"] < 750
    active_social = phase >= 2 or social_early
    add("social", "Kamernet / 社群 / 私人转租", "room · private · sublet · social channels", 5 if room else (4 if phase >= 2 else 2), "加强线" if phase >= 2 else ("主动补充" if active_social else "先建立信息源"), "later" if active_social else "passive", "加入本地群组并提高查看频率；优先联系可核验、条件匹配的房源" if active_social else "先加入信息源，但暂时不要占用主要找房时间", "中高" if phase >= 2 else ("中" if active_social else "低"), "主动权高、反馈快，但信息质量差异大。", "进入入住前约30–45天仍无进展时提高权重，并加强风险核验。")
    if profile["areaFlex"] == "maybe" and phase >= 2:
        add("radius", "周边城市搜索", "commute radius · nearby cities", 5, "现在扩围", "urgent", "把搜索半径扩大到可接受的通勤圈", "一次设置 + 每日", "当符合预算和身份的房源池太小，重复刷新不会明显增加机会。", "先定义可接受通勤上限，再扩围。")
    return result


def _effort(profile: dict, progress: dict, days: int, total: int) -> list[dict]:
    phase = _phase_index(days)
    student_minutes = 5 if _is_student(profile) else 0
    operator = min(20 if phase >= 2 else 15, max(5, round(total * 0.10)))
    if profile["homeType"] == "room" or phase >= 2:
        social = min(65 if phase >= 2 else 55, 8 + max(0, round((total - 30) * 0.33)))
    else:
        social = min(30, 5 + max(0, round((total - 30) * 0.12)))
    review = min(30, max(10, round(total * 0.18))) if progress["applications"] >= 15 and progress["viewings"] == 0 else 0
    commercial = max(5, total - student_minutes - operator - social - review)
    commercial += total - (student_minutes + operator + social + review + commercial)
    rows = []
    if student_minutes:
        rows.append(("student", "学生住房 / 学校线", student_minutes, "查看提醒 / 处理新机会"))
    rows.extend((("commercial", "综合租房平台", commercial, "设置提醒 / 熟悉筛选" if phase == 0 else "筛选新房源 / 提交申请"), ("operator", "住房运营商", operator, "查看提醒 / 快速检查库存"), ("social", "Room / 社群", social, "看新帖 / 主动联系" if profile["homeType"] == "room" or phase >= 2 else "观察信息 / 维护信息源")))
    if review:
        rows.append(("review", "资格 / 材料复盘", review, "检查门槛、材料和申请时机"))
    return [{"kind": kind, "name": name, "minutes": minutes, "percent": round(minutes / total * 100, 1), "action": action, "color": EFFORT_COLORS[kind]} for kind, name, minutes, action in rows]


def _progress_diagnosis(progress: dict) -> dict:
    if progress["confirmed"]:
        return {"title": "已记录确定住房。", "text": "策略将逐步降低找房渠道投入，转向签约、入住与后续事项。"}
    if progress["applications"] == 0:
        return {"title": "还没有真实申请数据。", "text": "当前策略主要根据身份、城市和时间生成；开始记录房源后，系统才能判断渠道覆盖和转化情况。"}
    if progress["applications"] >= 15 and progress["viewings"] == 0:
        return {"title": "申请有量，但还没有进入 Viewing。", "text": f"当前共记录 {progress['applications']} 套已联系或申请房源。先检查身份和收入门槛、材料、自我介绍与渠道适配。"}
    if progress["viewings"] >= 1:
        return {"title": "当前渠道已经产生有效反馈。", "text": f"已有 {progress['viewings']} 个 Viewing。继续保持有效渠道并重点跟进正在推进的房源。"}
    if progress["applications"] >= 6 and progress["replies"] == 0:
        return {"title": "回复率偏低。", "text": f"已记录 {progress['applications']} 套联系或申请，但没有回复。建议检查申请时机、条件匹配和渠道覆盖。"}
    return {"title": "策略开始读取真实反馈。", "text": f"当前 {progress['applications']} 套已联系或申请、{progress['replies']} 套收到回复、{progress['viewings']} 个 Viewing。"}


def generate(profile: dict, progress: dict, *, today: date | None = None) -> dict:
    """Return the complete strategy contract consumed by the browser renderer."""
    days = _days_to(profile["moveDate"], today)
    phase = _phase_index(days)
    channels = _channels(profile, progress, days)
    status = _status(days, progress)
    if progress["confirmed"]:
        plan_b = {"tone": "safe", "stage": "已确认", "title": "已确认住房，暂不需要 Plan B", "description": "系统已记录确定住房。正式签约完成前，仍建议保留必要跟进。"}
    elif days <= 14:
        plan_b = {"tone": "danger", "stage": "已启动", "title": "启动 Plan B，长期房继续申请", "description": "长期住房继续申请，同时确保抵达后有安全、合法的临时住宿。"}
    elif days <= 30 or (days <= 45 and progress["viewings"] == 0 and progress["applications"] >= 8):
        plan_b = {"tone": "warn", "stage": "准备中", "title": "开始准备 Plan B，长期房继续申请", "description": "建立2–3个可接受的临时住宿候选，避免最后几天被迫接受高风险房源。"}
    else:
        plan_b = {"tone": "safe", "stage": "暂不启动", "title": "当前以长期房申请为主", "description": "当前时间仍相对充足。进入关键窗口后，系统会根据真实进度提高警示。"}

    actions = []
    if progress["applications"] >= 15 and progress["viewings"] == 0:
        actions.append({"when": "今天", "title": "暂停无差别加量：先检查条件、材料与渠道适配", "tone": "hot"})
    if _is_student(profile) and profile["studentReg"] != "registered":
        actions.append({"when": "今天", "title": "完成学生住房注册 / 当地体系确认", "tone": "hot"})
    if _is_student(profile) and profile["universityHousing"] == "unknown":
        actions.append({"when": "今天", "title": "确认学校 University Housing 资格", "tone": ""})
    actions.append({"when": "今天" if phase == 0 else "每天", "title": "配置 Pararius / Funda 与运营商提醒" if phase == 0 else "优先申请符合条件的新房源", "tone": "hot" if phase >= 1 else ""})
    actions.append({"when": "本周", "title": "提高 Kamernet / 合租与本地社群覆盖" if profile["homeType"] == "room" or phase >= 2 else "把申请材料准备到可随时投递", "tone": ""})
    if phase >= 2 and profile["areaFlex"] == "maybe":
        actions.insert(0, {"when": "今天", "title": "把搜索范围扩到可接受的周边城市", "tone": "hot"})

    triggers = (
        "进入正式找房窗口后，商业平台会从配置提醒升为每日主战。",
        "进入约45天以内仍无明显进展时，社群、周边城市和Room渠道会提高权重。",
        "进入14天以内仍没有确定住房时，长期找房与落地住宿必须并行。",
        "当前已处于紧急落地窗口，策略不会再建议继续等待。",
    )
    explanation = f"距离预计入住还有 {days} 天，系统将等待型渠道和主动型渠道分开处理。"
    if _is_student(profile):
        explanation += " 学生住房已启动，因此保留为后台线路。" if profile["studentReg"] == "registered" else " 学生身份但学生住房尚未确认注册，因此被提升为一次性高优先动作。"
    explanation += " 主要寻找Room，人与人匹配和社群类渠道会更早提高权重。" if profile["homeType"] == "room" else " 主要寻找独立住房，商业平台与住房运营商权重更高。"
    if progress["applications"] >= 15 and progress["viewings"] == 0:
        explanation += " 当前进度显示联系或申请数量不低但没有Viewing，因此策略增加资格和材料复盘，而不是继续催促加量。"

    return {
        "engine_version": ENGINE_VERSION,
        "profile": profile,
        "progress": progress,
        "days": days,
        "phase": {"index": phase, "name": PHASES[phase]["name"], "copy": f"当前距离预计入住 {days} 天，位于“{PHASES[phase]['name']}”阶段。", "trigger": triggers[phase], "steps": list(PHASES)},
        "status": status,
        "plan_b": plan_b,
        "profile_chips": [IDENTITY_LABELS[profile["identity"]], profile["city"], HOME_LABELS[profile["homeType"]], f"预算 €{profile['budget']}", INCOME_LABELS[profile["income"]], f"预计入住 {profile['moveDate']}"],
        "top_actions": actions[:3],
        "channels": channels,
        "effort": [{"total": total, "rows": _effort(profile, progress, days, total)} for total in (30, 60, 90, 120, 150, 180)],
        "effort_copy": "随着可投入时间增加，等待型渠道保持低投入，新增时间主要给能产生申请和反馈的主动线路。",
        "progress_diagnosis": _progress_diagnosis(progress),
        "factors": [{"label": label, "value": value} for label, value in (("身份", IDENTITY_LABELS[profile["identity"]]), ("城市", profile["city"]), ("房型", HOME_LABELS[profile["homeType"]]), ("预算", f"€{profile['budget']}"), ("倒计时", f"{days} 天"), ("申请反馈", f"{progress['applications']} 联系或申请 / {progress['viewings']} Viewing" if progress["applications"] else "暂无数据"))],
        "explanation": explanation,
    }
