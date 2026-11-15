"""算法 B｜跟价建议（纯函数、确定性、只依赖标准库）。

输入：该 SKU 对标竞品近 N 天券后单件价列表、我方成本、底价、目标毛利、当前价与规则策略。

    分位数  P10 / P25 / P50 = 线性插值分位数（等价 numpy 默认 percentile）
    成本底线 cost_floor   = max(cost × (1 + 目标毛利%), 底价)
    市价上限 market_cap   = min(P25 × 1.02, 当前价)
    建议价   suggested    = min(max(...)) 说明见 build_advice：
                            hold 策略不动价；否则取 market_cap，
                            若 market_cap < cost_floor 则抬到 cost_floor（clamped_by=cost_floor），
                            最后再与底价取 max —— 任何情况下不破底价。

风险：触发「竞品券后价跌破我方底价」或「建议毛利 < 5%」→ high；
      降幅超过规则上限 max_drop_pct → medium；其余 low。
"""
from __future__ import annotations

MIN_GAP_PCT = 1.5
LOW_MARGIN_PCT = 5.0
HIGH_MARGIN_PCT = 15.0


def percentile(values: list[float], pct: float) -> float:
    """线性插值分位数；排序后 index = (n-1) × pct/100。"""
    if not values:
        raise ValueError("样本为空，无法计算分位数")
    data = sorted(float(value) for value in values)
    if len(data) == 1:
        return round(data[0], 4)
    if pct <= 0:
        return round(data[0], 4)
    if pct >= 100:
        return round(data[-1], 4)
    position = (len(data) - 1) * pct / 100.0
    lower = int(position)
    upper = min(lower + 1, len(data) - 1)
    weight = position - lower
    return round(data[lower] * (1 - weight) + data[upper] * weight, 4)


def _r2(value: float) -> float:
    return round(float(value) + 1e-12, 2)


def build_advice(
    *,
    competitor_prices: list[float],
    cost: float,
    floor_price: float,
    target_margin_pct: float,
    current_price: float,
    strategy: str = "guarded",
    max_drop_pct: float = 15.0,
    min_gap_pct: float = MIN_GAP_PCT,
) -> dict:
    prices = [float(value) for value in competitor_prices if value is not None and float(value) > 0]
    if not prices:
        raise ValueError("没有可比的竞品券后价")
    if current_price <= 0:
        raise ValueError("当前价必须大于 0")
    if cost < 0 or floor_price < 0:
        raise ValueError("成本与底价不能为负")

    p10 = percentile(prices, 10)
    p25 = percentile(prices, 25)
    p50 = percentile(prices, 50)
    mean = round(sum(prices) / len(prices), 4)

    cost_floor = _r2(max(cost * (1 + target_margin_pct / 100.0), floor_price))
    market_cap = _r2(min(p25 * 1.02, current_price))

    clamped_by = None
    if strategy == "hold":
        suggested = _r2(current_price)
        clamped_by = "hold"
    else:
        suggested = market_cap
        if market_cap < cost_floor:
            suggested = cost_floor
            clamped_by = "cost_floor"
    # 硬约束：建议价永远不低于底价
    if suggested < floor_price:
        suggested = _r2(floor_price)
        clamped_by = "floor_price"

    gap_pct = round((suggested - current_price) / current_price * 100.0, 2)
    margin_pct = round((suggested - cost) / suggested * 100.0, 2) if suggested > 0 else 0.0
    breach = market_cap < floor_price - 1e-9

    reasons: list[str] = []
    if breach:
        reasons.append(f"竞品券后价已低于我方底价 ¥{_fmt(floor_price)}，不能硬跟")
    if margin_pct < LOW_MARGIN_PCT:
        reasons.append(f"建议毛利仅 {margin_pct}%，低于 {LOW_MARGIN_PCT}%")
    if gap_pct < -max_drop_pct:
        reasons.append(f"降幅 {abs(gap_pct)}% 超过规则上限 {max_drop_pct}%")
    if clamped_by == "cost_floor":
        reasons.append("市价已压到成本底线，建议守成本线")
    if clamped_by == "hold":
        reasons.append("策略为只守不降，只记录差距不调价")
    if not reasons:
        reasons.append("竞品价与规则都在安全区间，按 P25 跟随")

    if breach or margin_pct < LOW_MARGIN_PCT:
        risk = "high"
    elif gap_pct < -max_drop_pct:
        risk = "medium"
    else:
        risk = "low"

    if gap_pct <= -0.5:
        action = "follow"
    elif gap_pct >= 0.5:
        action = "raise"
    else:
        action = "hold"

    need_follow = risk == "high" or abs(gap_pct) >= min_gap_pct
    reason = (
        f"竞品近{len(prices)}次券后价 P10/P25/P50 = ¥{_fmt(p10)} / ¥{_fmt(p25)} / ¥{_fmt(p50)}；"
        f"成本底线 ¥{_fmt(cost_floor)}，市价上限 ¥{_fmt(market_cap)}；"
        f"建议 ¥{_fmt(suggested)}（{gap_pct:+.2f}%），毛利 {margin_pct}%。" + " ".join(reasons)
    )
    return {
        "p10": p10,
        "p25": p25,
        "p50": p50,
        "mean": mean,
        "samples": len(prices),
        "cost_floor": cost_floor,
        "market_cap": market_cap,
        "suggested_price": suggested,
        "current_price": _r2(current_price),
        "gap_pct": gap_pct,
        "margin_pct": margin_pct,
        "risk": risk,
        "action": action,
        "clamped_by": clamped_by,
        "breach": breach,
        "need_follow": need_follow,
        "reason": reason,
        "reasons": reasons,
        "strategy": strategy,
        "max_drop_pct": max_drop_pct,
        "target_margin_pct": target_margin_pct,
    }


def _fmt(value: float) -> str:
    return ("%.2f" % value).rstrip("0").rstrip(".")
