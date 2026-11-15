"""共享枚举（后端唯一定义处）。前端副本见 frontend/site/js/config.js。

README「共享枚举出现位置」一节列出全部出现点，改动需两侧同步。
"""
from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


class Platform(StrEnum):
    """竞品店铺所在平台（决定券的种类与叠加方式）。"""

    DOUYIN = "douyin"
    TAOBAO = "taobao"
    JD = "jd"
    PDD = "pdd"
    XHS = "xhs"
    WEIDIAN = "weidian"


PLATFORM_LABELS: dict[str, str] = {
    Platform.DOUYIN.value: "抖音小店",
    Platform.TAOBAO.value: "天猫 / 淘宝",
    Platform.JD.value: "京东",
    Platform.PDD.value: "拼多多",
    Platform.XHS.value: "小红书",
    Platform.WEIDIAN.value: "微店",
}


class Category(StrEnum):
    SOFA = "sofa"
    TABLE = "table"
    BED = "bed"
    CABINET = "cabinet"
    DECOR = "decor"


CATEGORY_LABELS: dict[str, str] = {
    Category.SOFA.value: "沙发",
    Category.TABLE.value: "桌几",
    Category.BED.value: "床具",
    Category.CABINET.value: "柜类",
    Category.DECOR.value: "软装",
}


class RuleStrategy(StrEnum):
    """跟价策略：决定建议价锚点如何被规则改写。"""

    GUARDED = "guarded"  # 有底线跟价：跟到 P25×1.02，但不破成本/底价
    AGGRESSIVE = "aggressive"  # 抢量：目标毛利压低，跟随更紧
    HOLD = "hold"  # 只守不降：维持当前价，仅记录竞品差


RULE_STRATEGY_LABELS: dict[str, str] = {
    RuleStrategy.GUARDED.value: "有底线跟价",
    RuleStrategy.AGGRESSIVE.value: "抢量紧跟",
    RuleStrategy.HOLD.value: "只守不降",
}


class RiskLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


RISK_LABELS: dict[str, str] = {
    RiskLevel.HIGH.value: "高风险",
    RiskLevel.MEDIUM.value: "中风险",
    RiskLevel.LOW.value: "低风险",
}

RISK_ORDER: list[str] = [RiskLevel.HIGH.value, RiskLevel.MEDIUM.value, RiskLevel.LOW.value]


class AdviceStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


ADVICE_STATUS_LABELS: dict[str, str] = {
    AdviceStatus.PENDING.value: "待审批",
    AdviceStatus.APPROVED.value: "已批改价",
    AdviceStatus.REJECTED.value: "已驳回",
}

ADVICE_STATUS_ORDER: list[str] = [
    AdviceStatus.PENDING.value,
    AdviceStatus.APPROVED.value,
    AdviceStatus.REJECTED.value,
]


class AdviceAction(StrEnum):
    """建议动作（算法 B 输出，页面与导出共用）。"""

    FOLLOW = "follow"
    HOLD = "hold"
    RAISE = "raise"


ADVICE_ACTION_LABELS: dict[str, str] = {
    AdviceAction.FOLLOW.value: "跟价下调",
    AdviceAction.HOLD.value: "维持不动",
    AdviceAction.RAISE.value: "回调上行",
}


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


RUN_STATUS_LABELS: dict[str, str] = {
    RunStatus.QUEUED.value: "排队中",
    RunStatus.RUNNING.value: "执行中",
    RunStatus.SUCCESS.value: "成功",
    RunStatus.PARTIAL.value: "部分成功",
    RunStatus.FAILED.value: "失败",
}


class TriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    SEED = "seed"


TRIGGER_LABELS: dict[str, str] = {
    TriggerKind.MANUAL.value: "手动",
    TriggerKind.SCHEDULE.value: "定时",
    TriggerKind.SEED.value: "初始化",
}


class CouponKind(StrEnum):
    """券后价还原涉及的折扣类型。"""

    FULL_REDUCTION = "full_reduction"  # 满减阶梯（单档命中）
    SHOP_COUPON = "shop_coupon"  # 店铺券（可与满减叠加）
    PLATFORM_COUPON = "platform_coupon"  # 平台跨店券（每满 X 减 Y，可重复）
    MEMBER_DISCOUNT = "member_discount"  # 会员折扣率


COUPON_KIND_LABELS: dict[str, str] = {
    CouponKind.FULL_REDUCTION.value: "满减",
    CouponKind.SHOP_COUPON.value: "店铺券",
    CouponKind.PLATFORM_COUPON.value: "平台券",
    CouponKind.MEMBER_DISCOUNT.value: "会员折扣",
}
