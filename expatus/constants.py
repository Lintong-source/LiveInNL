"""Stable product catalog and rental-progress vocabulary shared by all layers."""

STATUSES = [
    "待处理",
    "已表达意向",
    "准备申请材料",
    "已提交申请",
    "已收到回复",
    "已预约看房",
    "已签约",
]

PROGRESS_PERCENT = {
    "待处理": 0,
    "已表达意向": 15,
    "准备申请材料": 30,
    "已提交申请": 50,
    "已收到回复": 65,
    "已预约看房": 82,
    "已签约": 100,
}

STAGE_DESCRIPTIONS = {
    "待处理": "这套房源已经加入记录，可以从这里继续跟进。",
    "已表达意向": "已经通过消息、报名或其他方式对这套房源表达兴趣。",
    "准备申请材料": "这套房源已经进入申请材料准备阶段。",
    "已提交申请": "申请已经提交，目前等待后续结果。",
    "已收到回复": "已经收到房东、中介或住房机构对这套房源的有效回复。",
    "已预约看房": "已经获得看房邀请，或已预约、完成这套房源的 Viewing。",
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

# Keep server-rendered favorites visually aligned with the existing homepage utilities.
PLATFORM_AVATAR_KEYS = {
    "ROOM.nl": "room",
    "DUWO": "duwo",
    "SSH": "ssh",
    "Xior Student Housing": "xior",
    "Vestide": "vesteda",
    "Maastricht Housing": "mvgm",
    "Holland2Stay": "holland2stay",
    "Pararius": "pararius",
    "Funda": "funda",
    "Kamernet": "kamernet",
    "Huurwoningen.nl": "huurwoningen",
    "HousingAnywhere": "housinganywhere",
    "Nestpick": "neste",
    "Facebook 租房群": "facebook",
    "Airbnb 月租": "airbnb",
}
