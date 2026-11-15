"""算法 A｜券后有效价还原单测：验收样例 + 边界 + 确定性。"""
from __future__ import annotations

import pytest

from src.services.effective_price import compute_effective_price

SHOWPIECE = {
    "page_price": 299.0,
    "full_reduction": [{"threshold": 300.0, "minus": 40.0}],
    "shop_coupon": {"threshold": 200.0, "minus": 20.0, "stackable": True},
    "platform_coupon": {"per": 300.0, "minus": 50.0},
    "member_discount": 1.0,
}


def test_showpiece_matches_hand_calculation():
    """验收：299 元 + 满300减40 + 店铺券20 + 平台每满300减50。"""
    result = compute_effective_price(SHOWPIECE)
    assert result["valid"] is True
    # n=1：满减不触发（299 < 300）→ 299 - 20 = 279
    assert result["unit_price_1"] == 279.0
    # n=2：598 - 40 - 20 - 50 = 488 → 单价 244
    assert result["unit_price_2"] == 244.0
    # n=3：897 - 40 - 20 - 100 = 737 → 单价 245.67
    assert result["unit_price_3"] == 245.67
    assert result["best_units"] == 2
    assert result["best_unit_price"] == 244.0
    assert "满300减40" in result["note"] and "平台券" in result["note"]


def test_no_coupon_equals_page_price():
    result = compute_effective_price({"page_price": 1299.0})
    assert result["valid"] is True
    assert result["unit_price_1"] == 1299.0
    assert result["unit_price_2"] == 1299.0
    assert result["unit_price_3"] == 1299.0
    assert result["warnings"]


def test_member_discount_applies_after_coupons():
    result = compute_effective_price(
        {
            "page_price": 1000.0,
            "full_reduction": [{"threshold": 900.0, "minus": 100.0}],
            "member_discount": 0.9,
        }
    )
    # (1000 - 100) × 0.9 = 810
    assert result["unit_price_1"] == pytest.approx(810.0)


def test_tier_uses_highest_matching_threshold():
    result = compute_effective_price(
        {
            "page_price": 400.0,
            "full_reduction": [
                {"threshold": 300.0, "minus": 30.0},
                {"threshold": 600.0, "minus": 90.0},
            ],
        }
    )
    assert result["unit_price_1"] == 370.0
    # 800 元命中 600 档，减 90
    assert result["unit_price_2"] == 355.0


def test_non_stackable_shop_coupon_picks_better_discount():
    result = compute_effective_price(
        {
            "page_price": 600.0,
            "shop_coupon": {"threshold": 500.0, "minus": 30.0, "stackable": False},
            "platform_coupon": {"per": 300.0, "minus": 50.0},
        }
    )
    # 平台券 2×50=100 优于店铺券 30 → 600 - 100 = 500
    assert result["unit_price_1"] == 500.0
    assert result["units"][0]["coupon_choice"] == "platform_coupon"


def test_numeric_strings_are_coerced():
    result = compute_effective_price({"page_price": "299.00", "full_reduction": [{"threshold": "300", "minus": "40"}]})
    assert result["unit_price_1"] == 299.0


@pytest.mark.parametrize(
    "spec",
    [
        {"page_price": 0},
        {"page_price": -5},
        {"page_price": None},
        {"page_price": 100, "member_discount": 1.4},
        {"page_price": 100, "full_reduction": [{"threshold": -1, "minus": 10}]},
        {"page_price": 100, "shop_coupon": {"threshold": 50, "minus": 80}},
        {"page_price": 100, "platform_coupon": {"per": 0, "minus": 5}},
    ],
)
def test_invalid_spec_returns_failure(spec):
    result = compute_effective_price(spec)
    assert result["valid"] is False
    assert result["error"] == "INVALID_SNAPSHOT"
    assert result["unit_price_1"] is None


def test_deterministic():
    first = compute_effective_price(SHOWPIECE)
    second = compute_effective_price(SHOWPIECE)
    assert first == second
