"""演示账号与种子数据（确定性生成，不依赖 random，任何机器上两次执行逐字一致）。

口径：
  6 个竞品店铺（种子里的 sources 计数）
  320 个自有 SKU，按 i % 5 分到 5 个类目、i % 6 对标到 6 个竞品店铺
  960 条抓价快照 = 320 SKU × 近 3 天
  42 个 SKU 的竞品券后价明显低于我方当前价（需要跟价），其中 9 个会命中高风险
  1 次测算运行产出 42 条建议

价格基线按类目给定区间；同一 SKU 三天的价格因子固定，保证算法 B 的分位数稳定。
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

DEMO_PASSWORD = "Demo@2026"

DEMO_USERS = [
    ("admin@pricewatch.io", "林可 · 定价主管", "admin"),
    ("analyst@pricewatch.io", "周棠 · 价格运营", "analyst"),
    ("viewer@pricewatch.io", "陈默 · 店长只读", "viewer"),
]

ORG = "泊岸家居 · 电商定价组"
BRAND = "pricewatch"

COMPETITORS = [
    {
        "code": "dy-muyan",
        "name": "抖音 · 木言家居旗舰店",
        "platform": "douyin",
        "shop_url": "https://shop.douyin.example/muyan",
        "region": "华东",
        "note": "店播频繁改价，券后价常低于页面价 8%~12%",
        "capture_config": {"replay": "fixture/dy-muyan", "cron": "0 8,20 * * *", "headers": {"ua": "pricewatch-rpa/2.1"}},
    },
    {
        "code": "tb-beian",
        "name": "天猫 · 北岸家居专营店",
        "platform": "taobao",
        "shop_url": "https://shop.tmall.example/beian",
        "region": "华东",
        "note": "满减阶梯 3 档，店铺券可叠加平台跨店券",
        "capture_config": {"replay": "fixture/tb-beian", "cron": "0 9,21 * * *", "headers": {"ua": "pricewatch-rpa/2.1"}},
    },
    {
        "code": "jd-yuanmu",
        "name": "京东 · 原木纪官方旗舰店",
        "platform": "jd",
        "shop_url": "https://shop.jd.example/yuanmu",
        "region": "华北",
        "note": "价格稳定，会员价另算，跟随幅度小",
        "capture_config": {"replay": "fixture/jd-yuanmu", "cron": "30 9,21 * * *", "headers": {"ua": "pricewatch-rpa/2.1"}},
    },
    {
        "code": "pdd-huiju",
        "name": "拼多多 · 惠居工厂店",
        "platform": "pdd",
        "shop_url": "https://shop.pdd.example/huiju",
        "region": "华南",
        "note": "百亿补贴位波动大，需按件数拆算",
        "capture_config": {"replay": "fixture/pdd-huiju", "cron": "0 10,22 * * *", "headers": {"ua": "pricewatch-rpa/2.1"}},
    },
    {
        "code": "xhs-qijian",
        "name": "小红书 · 栖间家居",
        "platform": "xhs",
        "shop_url": "https://shop.xhs.example/qijian",
        "region": "华东",
        "note": "以笔记挂链为主，页面价偏高、券少",
        "capture_config": {"replay": "fixture/xhs-qijian", "cron": "0 11,23 * * *", "headers": {"ua": "pricewatch-rpa/2.1"}},
    },
    {
        "code": "wd-nanmu",
        "name": "微店 · 南木生活",
        "platform": "weidian",
        "shop_url": "https://shop.weidian.example/nanmu",
        "region": "西南",
        "note": "小店主手工改价，抓价失败率约 3%",
        "capture_config": {"replay": "fixture/wd-nanmu", "cron": "0 12 * * *", "headers": {"ua": "pricewatch-rpa/2.1"}},
    },
]

CATEGORIES = ["sofa", "table", "bed", "cabinet", "decor"]

CATEGORY_BASE = {
    "sofa": (1299, 4599),
    "table": (399, 1699),
    "bed": (1699, 5999),
    "cabinet": (499, 2299),
    "decor": (99, 599),
}

CATEGORY_NAMES = {
    "sofa": ["云栖", "松间", "叶影", "南山", "拾光", "半野"],
    "table": ["石阶", "木隼", "长汀", "方寸", "砚台"],
    "bed": ["月栖", "归巢", "原上", "无声", "春榻"],
    "cabinet": ["格物", "叠山", "简序", "榫间", "岸线"],
    "decor": ["灯语", "织间", "风铃", "陶白", "穗影"],
}

CATEGORY_ITEMS = {
    "sofa": ["三人位布艺沙发", "双人位皮沙发", "转角组合沙发", "单人休闲椅", "模块沙发"],
    "table": ["实木餐桌 1.4m", "岩板茶几", "折叠边几", "书桌 1.2m", "圆餐台"],
    "bed": ["实木双人床 1.8m", "软包床 1.5m", "高箱储物床", "儿童床 1.2m", "床架 1.8m"],
    "cabinet": ["两门衣柜", "餐边柜", "床头柜", "电视柜 1.8m", "玄关柜"],
    "decor": ["落地灯", "羊毛地毯", "陶瓷花器", "亚麻窗帘", "装饰画组"],
}

RULE_SPECS = [
    {
        "code": "rule-global",
        "name": "全局默认：有底线跟价",
        "scope_kind": "global",
        "scope_value": "",
        "strategy": "guarded",
        "target_margin_pct": 12.0,
        "max_drop_pct": 15.0,
        "priority": 100,
        "note": "所有未命中专门规则的 SKU 都走这条",
    },
    {
        "code": "rule-douyin",
        "name": "抖音店播抢量：紧跟",
        "scope_kind": "competitor",
        "scope_value": "dy-muyan",
        "strategy": "aggressive",
        "target_margin_pct": 8.0,
        "max_drop_pct": 15.0,
        "priority": 40,
        "note": "店播价格变动快，允许更紧的跟随",
    },
    {
        "code": "rule-jd",
        "name": "京东守毛利：缓跟",
        "scope_kind": "competitor",
        "scope_value": "jd-yuanmu",
        "strategy": "guarded",
        "target_margin_pct": 12.0,
        "max_drop_pct": 12.0,
        "priority": 40,
        "note": "京东价稳，降幅上限压到 12%",
    },
    {
        "code": "rule-decor-hold",
        "name": "软装类目只守不降",
        "scope_kind": "category",
        "scope_value": "decor",
        "strategy": "hold",
        "target_margin_pct": 20.0,
        "max_drop_pct": 0.0,
        "priority": 30,
        "note": "软装客单低、券少，不参与跟价",
    },
    {
        "code": "rule-sku-showpiece",
        "name": "云栖三人位沙发：手算校验样例",
        "scope_kind": "sku",
        "scope_value": "PB-sofa-001",
        "strategy": "guarded",
        "target_margin_pct": 12.0,
        "max_drop_pct": 15.0,
        "priority": 10,
        "note": "验收用：页面价 299 + 满300减40 + 店铺券20 + 平台每满300减50",
    },
]

SKU_COUNT = 320
FOLLOW_COUNT = 42
HIGH_COUNT = 9
MEDIUM_COUNT = 13
CAPTURE_DAYS = 3

# 验收样例：页面价 299、满300减40（n=1 不触发）、店铺券满200减20、平台每满300减50
SHOWPIECE_CODE = "PB-sofa-001"
SHOWPIECE_SPEC = {
    "page_price": 299.0,
    "full_reduction": [{"threshold": 300.0, "minus": 40.0}],
    "shop_coupon": {"threshold": 200.0, "minus": 20.0, "stackable": True, "label": "店铺券"},
    "platform_coupon": {"per": 300.0, "minus": 50.0, "label": "跨店每满300减50"},
    "member_discount": 1.0,
}

# 三类跟价桶：竞品券后价因子（相对我方当前价），成本/底价/目标毛利占比
BUCKETS = {
    "high": {"factors": (0.84, 0.86, 0.88), "cost": 0.86, "floor": 0.90, "margin": 12.0},
    "medium": {"factors": (0.80, 0.82, 0.84), "cost": 0.55, "floor": 0.72, "margin": 15.0},
    "low": {"factors": (0.92, 0.94, 0.96), "cost": 0.60, "floor": 0.75, "margin": 15.0},
    "base": {"factors": (0.996, 1.0, 1.004), "cost": 0.55, "floor": 0.72, "margin": 15.0},
}


def _money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _follow_indexes() -> list[int]:
    """42 个需要跟价的 SKU 下标：跳过软装类目（该类目规则是只守不降），避免口径互相干扰。"""
    picked: list[int] = []
    for index in range(SKU_COUNT):
        if index % len(CATEGORIES) == CATEGORIES.index("decor"):
            continue
        if index == 0:
            continue  # 0 号是验收样例，单独处理
        picked.append(index)
        if len(picked) >= FOLLOW_COUNT - 1:
            break
    return picked


def _bucket_of(index: int, follow: list[int]) -> str:
    if index not in follow:
        return "base"
    position = follow.index(index)
    if position < HIGH_COUNT:
        return "high"
    if position < HIGH_COUNT + MEDIUM_COUNT:
        return "medium"
    return "low"


def build_skus() -> list[dict]:
    follow = _follow_indexes()
    skus: list[dict] = []
    for index in range(SKU_COUNT):
        category = CATEGORIES[index % len(CATEGORIES)]
        competitor = COMPETITORS[index % len(COMPETITORS)]
        low, high = CATEGORY_BASE[category]
        base = low + (index * 37) % max(1, high - low)
        bucket = "low" if index == 0 else _bucket_of(index, follow)
        spec = BUCKETS[bucket]
        name_a = CATEGORY_NAMES[category][index % len(CATEGORY_NAMES[category])]
        name_b = CATEGORY_ITEMS[category][index % len(CATEGORY_ITEMS[category])]
        current = 319.0 if index == 0 else float(round(base))
        skus.append(
            {
                "sku_code": f"PB-{category}-{index + 1:03d}",
                "name": f"{name_a}{name_b}",
                "category": category,
                "competitor_code": competitor["code"],
                "competitor_item_id": f"{competitor['code'].upper()}-{index * 13 % 9000 + 1000}",
                "unit": "件",
                "cost": round(current * spec["cost"], 2),
                "floor_price": round(current * spec["floor"], 2),
                "target_margin_pct": spec["margin"],
                "current_price": current,
                "stock": 12 + (index * 7) % 90,
                "bucket": bucket,
                "index": index,
                "note": "竞品券后价明显低于我方" if bucket in ("high", "medium", "low") else "",
            }
        )
    return skus


def build_snapshot(sku: dict, day_offset: int) -> dict:
    """day_offset: 0=今天、1=昨天、2=前天。返回快照字段（含算法 A 输入 spec）。"""
    factors = BUCKETS[sku["bucket"]]["factors"]
    factor = factors[2 - day_offset]  # 前天→今天因子递增（竞品逐步降价）
    if sku["sku_code"] == SHOWPIECE_CODE:
        spec = dict(SHOWPIECE_SPEC)
        spec["page_price"] = SHOWPIECE_SPEC["page_price"]
        return {
            "captured_on_offset": day_offset,
            "page_price": spec["page_price"],
            "full_reduction": spec["full_reduction"],
            "shop_coupon": spec["shop_coupon"],
            "platform_coupon": spec["platform_coupon"],
            "member_discount": 1.0,
            "campaign": ["618 预热", "618 开门红", "618 现货"][day_offset],
            "stock": sku["stock"] + day_offset,
            "spec": spec,
        }

    current = sku["current_price"]
    if sku["bucket"] == "base" and sku["index"] % 7 == 0:
        # 一部分常规 SKU 叠加会员 95 折：把页面价抬高，使券后价≈我方当前价（不给跟价建议）
        page = _money(current / 0.95)
        spec = {
            "page_price": page,
            "full_reduction": [],
            "shop_coupon": None,
            "platform_coupon": None,
            "member_discount": 0.95,
        }
    elif sku["bucket"] == "base":
        page = _money(current * factor)
        spec = {
            "page_price": page,
            "full_reduction": [],
            "shop_coupon": None,
            "platform_coupon": None,
            "member_discount": 1.0,
        }
    else:
        page = _money(current * factor + 20.0)  # 店铺券满200减20，券后 ≈ current × factor
        spec = {
            "page_price": page,
            "full_reduction": [],
            "shop_coupon": {"threshold": 200.0, "minus": 20.0, "stackable": True, "label": "店铺券"},
            "platform_coupon": None,
            "member_discount": 1.0,
        }
    return {
        "captured_on_offset": day_offset,
        "page_price": spec["page_price"],
        "full_reduction": spec["full_reduction"],
        "shop_coupon": spec["shop_coupon"],
        "platform_coupon": spec["platform_coupon"],
        "member_discount": spec["member_discount"],
        "campaign": ["618 预热", "618 开门红", "618 现货"][day_offset],
        "stock": sku["stock"] + day_offset,
        "spec": spec,
    }


def build_dataset() -> dict:
    skus = build_skus()
    snapshots = []
    for sku in skus:
        for day_offset in range(CAPTURE_DAYS):
            snap = build_snapshot(sku, day_offset)
            snap["sku_code"] = sku["sku_code"]
            snap["competitor_code"] = sku["competitor_code"]
            snapshots.append(snap)
    return {
        "competitors": COMPETITORS,
        "skus": skus,
        "rules": RULE_SPECS,
        "snapshots": snapshots,
        "capture_days": CAPTURE_DAYS,
        "run_seed_key": "seed-run-capture-today",
    }
