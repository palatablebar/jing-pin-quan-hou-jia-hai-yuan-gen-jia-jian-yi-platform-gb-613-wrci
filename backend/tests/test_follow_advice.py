"""算法 B｜跟价建议单测：分位数、底价约束、风险分层、确定性。"""
from __future__ import annotations

import pytest

from src.services.follow_advice import build_advice, percentile


def test_percentile_linear_interpolation():
    values = [100, 200, 300, 400]
    assert percentile(values, 0) == 100
    assert percentile(values, 50) == pytest.approx(250.0)
    assert percentile(values, 100) == 400
    assert percentile([279.0, 279.0, 279.0], 25) == pytest.approx(279.0)


def test_guarded_follow_uses_p25_cap():
    result = build_advice(
        competitor_prices=[273.0, 279.0, 285.0],
        cost=191.4,
        floor_price=239.25,
        target_margin_pct=12,
        current_price=319.0,
    )
    # P25 = 276 → ×1.02 = 281.52，低于当前价 319 → 建议 281.52
    assert result["p25"] == pytest.approx(276.0)
    assert result["suggested_price"] == pytest.approx(281.52)
    assert result["suggested_price"] >= result["current_price"] * 0
    assert result["action"] == "follow"
    assert result["risk"] == "low"
    assert result["need_follow"] is True


def test_market_cap_follows_p25_and_keeps_floor():
    result = build_advice(
        competitor_prices=[250.0, 255.0, 260.0],
        cost=220.0,
        floor_price=240.0,
        target_margin_pct=12,
        current_price=300.0,
    )
    # P25 = 252.5 → 市价上限 252.5×1.02 = 257.55 > 成本底线 246.4 → 建议 257.55
    assert result["p25"] == pytest.approx(252.5)
    assert result["suggested_price"] == pytest.approx(257.55)
    assert result["suggested_price"] >= result["cost_floor"]
    assert result["margin_pct"] == pytest.approx(14.58)
    assert result["breach"] is False
    assert result["risk"] == "low"


def test_cost_floor_clamp_keeps_margin():
    result = build_advice(
        competitor_prices=[240.0, 245.0, 250.0],
        cost=230.0,
        floor_price=225.0,
        target_margin_pct=12,
        current_price=300.0,
    )
    # P25 = 242.5 → 市价上限 247.35 < 成本底线 257.6 → 抬到成本底线
    assert result["suggested_price"] == pytest.approx(257.6)
    assert result["clamped_by"] == "cost_floor"
    assert result["margin_pct"] == pytest.approx(10.71)
    assert result["breach"] is False


def test_floor_breach_explicit():
    result = build_advice(
        competitor_prices=[200.0, 210.0, 220.0],
        cost=180.0,
        floor_price=230.0,
        target_margin_pct=12,
        current_price=300.0,
    )
    # 市价上限 214.2 < 底价 230 → 破底价 → 建议守底价 230，风险 high
    assert result["suggested_price"] == pytest.approx(230.0)
    assert result["breach"] is True
    assert result["risk"] == "high"
    assert "低于我方底价" in result["reason"]


def test_low_margin_is_high_risk():
    result = build_advice(
        competitor_prices=[310.0, 315.0, 320.0],
        cost=310.0,
        floor_price=280.0,
        target_margin_pct=2,
        current_price=330.0,
    )
    assert result["margin_pct"] < 5
    assert result["risk"] == "high"


def test_big_drop_is_medium_risk():
    result = build_advice(
        competitor_prices=[255.0, 260.0, 265.0],
        cost=150.0,
        floor_price=180.0,
        target_margin_pct=12,
        current_price=330.0,
        max_drop_pct=15,
    )
    # 建议 265.2 → gap -19.6% < -15 → medium
    assert result["gap_pct"] < -15
    assert result["risk"] == "medium"


def test_hold_strategy_keeps_current_price():
    result = build_advice(
        competitor_prices=[250.0, 260.0, 270.0],
        cost=150.0,
        floor_price=180.0,
        target_margin_pct=12,
        current_price=330.0,
        strategy="hold",
    )
    assert result["suggested_price"] == pytest.approx(330.0)
    assert result["action"] == "hold"
    assert result["clamped_by"] == "hold"
    assert result["need_follow"] is False


def test_no_competitor_price_raises():
    with pytest.raises(ValueError):
        build_advice(
            competitor_prices=[],
            cost=1,
            floor_price=1,
            target_margin_pct=10,
            current_price=10,
        )


def test_deterministic():
    kwargs = dict(
        competitor_prices=[249.0, 255.0, 261.0],
        cost=180.0,
        floor_price=205.0,
        target_margin_pct=12,
        current_price=299.0,
    )
    assert build_advice(**kwargs) == build_advice(**kwargs)
