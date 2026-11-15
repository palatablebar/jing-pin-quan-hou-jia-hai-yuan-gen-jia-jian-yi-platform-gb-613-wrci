"""可售状态口径：缺货/下架报价保留但不进跟价样本；失效建议保留不删除。

纯函数测试（不连数据库）：collect_sellable_quotes 的分组与排除原因、
种子数据的可售分布、缺货样本对算法 B 分位数的影响。
"""
from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from scripts.demo_config import SHOWPIECE_CODE, build_dataset
from src.services import effective_price, follow_advice, pricing_service


def _snapshot(
    snapshot_id: int,
    sku_id: int,
    day: date,
    *,
    availability: str = "in_stock",
    valid: bool = True,
    unit_price_1: float | None = 279.0,
    page_price: float = 299.0,
    stock: int = 10,
):
    return SimpleNamespace(
        id=snapshot_id,
        sku_id=sku_id,
        captured_on=day,
        page_price=page_price,
        stock=stock,
        source_url="https://shop.example/item/1",
        availability=availability,
        effective={"valid": valid, "unit_price_1": unit_price_1},
    )


def test_collect_sellable_quotes_splits_and_keeps_reasons():
    today = date(2026, 11, 15)
    window = [
        _snapshot(1, 7, today, unit_price_1=279.0),
        _snapshot(2, 7, today - timedelta(days=1), availability="out_of_stock", stock=0, unit_price_1=199.0),
        _snapshot(3, 7, today - timedelta(days=2), availability="delisted", stock=0, unit_price_1=189.0),
        _snapshot(4, 7, today - timedelta(days=2), valid=False, unit_price_1=None),
    ]
    groups = pricing_service.collect_sellable_quotes(window)
    group = groups[7]
    # 只有现货可售的报价进样本；缺货/下架/非法报价都进排除清单且带原因
    assert [quote["snapshot_id"] for quote in group["sellable"]] == [1]
    excluded = {quote["snapshot_id"]: quote for quote in group["excluded"]}
    assert set(excluded) == {2, 3, 4}
    assert excluded[2]["kind"] == "unsellable" and "缺货" in excluded[2]["reason"]
    assert excluded[3]["kind"] == "unsellable" and "下架" in excluded[3]["reason"]
    assert excluded[4]["kind"] == "invalid" and excluded[4]["reason"]
    # 排除的报价仍保留价格证据（快照不丢）
    assert excluded[2]["unit_price_1"] == 199.0
    assert excluded[3]["page_price"] == 299.0


def test_unsellable_low_quotes_do_not_drag_samples():
    """缺货的低价报价不再拉低 P25：样本只含可成交报价。"""
    sellable = [279.0, 285.0]
    with_oos_low = [279.0, 285.0, 189.0]  # 缺货低价若混入会显著拉低分位数
    kept = follow_advice.build_advice(
        competitor_prices=sellable,
        cost=191.4,
        floor_price=239.25,
        target_margin_pct=12,
        current_price=319.0,
    )
    dragged = follow_advice.build_advice(
        competitor_prices=with_oos_low,
        cost=191.4,
        floor_price=239.25,
        target_margin_pct=12,
        current_price=319.0,
    )
    assert kept["p25"] == pytest.approx(280.5)
    assert dragged["p25"] < kept["p25"]
    assert kept["suggested_price"] > dragged["suggested_price"]


def test_seed_unsellable_snapshots_are_base_bucket_only():
    """种子里的缺货/下架快照只落在不出建议的 SKU 上，42 条建议口径不变。"""
    dataset = build_dataset()
    skus = {spec["sku_code"]: spec for spec in dataset["skus"]}
    unsellable = [snap for snap in dataset["snapshots"] if snap.get("availability", "in_stock") != "in_stock"]
    assert unsellable, "种子应自带缺货/下架样本用于演示排除证据"
    for snap in unsellable:
        assert skus[snap["sku_code"]]["bucket"] == "base"
        assert snap["stock"] == 0
        assert snap["availability_note"]
    # 每条快照都带可售状态（逐条保留）
    assert all("availability" in snap for snap in dataset["snapshots"])


def test_seed_showpiece_stays_fully_sellable():
    dataset = build_dataset()
    showpiece = [snap for snap in dataset["snapshots"] if snap["sku_code"] == SHOWPIECE_CODE]
    assert len(showpiece) == 3
    assert all(snap["availability"] == "in_stock" for snap in showpiece)
    effective = effective_price.compute_effective_price(showpiece[0]["spec"])
    assert (effective["unit_price_1"], effective["unit_price_2"], effective["unit_price_3"]) == (279.0, 244.0, 245.67)


def test_collect_groups_are_deterministic():
    today = date(2026, 11, 15)
    window = [
        _snapshot(1, 3, today - timedelta(days=2), unit_price_1=270.0),
        _snapshot(2, 3, today - timedelta(days=1), availability="out_of_stock", stock=0),
        _snapshot(3, 3, today, unit_price_1=280.0),
    ]
    first = pricing_service.collect_sellable_quotes(list(window))
    second = pricing_service.collect_sellable_quotes(list(window))
    assert first == second
