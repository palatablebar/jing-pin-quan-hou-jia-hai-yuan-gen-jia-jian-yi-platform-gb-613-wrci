"""测算主流程集成测试（SQLite 内存库，不依赖 PostgreSQL）：

  - 缺货/下架快照保留但不进跟价样本，建议 payload 带可售证据与排除原因；
  - 同一测算（同快照日）重跑复用原运行，不新增建议；
  - 上游可售状态同步后，相关建议失效并同步重算，建议总数不变。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base
from src.models.advice import Advice
from src.models.competitor import Competitor
from src.models.rule import Rule
from src.models.run import Run
from src.models.sku import Sku
from src.models.snapshot import Snapshot
from src.services import availability_service, effective_price, pricing_service

TODAY = date(2026, 11, 15)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)
    session = factory()
    yield session
    session.close()


def _catalog(db: Session) -> tuple[Competitor, Sku, list[Snapshot]]:
    competitor = Competitor(code="tb-test", name="天猫 · 测试店", platform="taobao", enabled=True)
    db.add(competitor)
    db.flush()
    sku = Sku(
        sku_code="PB-sofa-901",
        name="测试三人位沙发",
        category="sofa",
        competitor_id=competitor.id,
        cost=191.4,
        floor_price=239.25,
        target_margin_pct=12.0,
        current_price=319.0,
        stock=20,
        enabled=True,
    )
    db.add(sku)
    db.add(
        Rule(
            code="rule-global",
            name="全局默认",
            scope_kind="global",
            scope_value="",
            strategy="guarded",
            target_margin_pct=12.0,
            max_drop_pct=15.0,
            priority=100,
            enabled=True,
        )
    )
    db.flush()
    snapshots = []
    for offset in (2, 1, 0):
        spec = {
            "page_price": 299.0,
            "full_reduction": [],
            "shop_coupon": {"threshold": 200.0, "minus": 20.0, "stackable": True},
            "platform_coupon": None,
            "member_discount": 1.0,
        }
        snapshot = Snapshot(
            sku_id=sku.id,
            competitor_id=competitor.id,
            captured_on=TODAY - timedelta(days=offset),
            page_price=299.0,
            full_reduction=[],
            shop_coupon=spec["shop_coupon"],
            platform_coupon=None,
            member_discount=1.0,
            stock=10,
            availability="in_stock",
            campaign="测试回放",
            effective=effective_price.compute_effective_price(spec),
        )
        db.add(snapshot)
        snapshots.append(snapshot)
    db.flush()
    return competitor, sku, snapshots


def _run_once(db: Session) -> Run:
    return pricing_service.compute_run(db, captured_on=TODAY, operator_email="analyst@pricewatch.io")


def _only_advice(db: Session) -> Advice:
    return db.scalar(select(Advice).where(Advice.sku_id == 1))


def test_run_builds_advice_with_sellable_evidence(db):
    _catalog(db)
    run = _run_once(db)
    advice = _only_advice(db)
    assert run.status == "success"
    assert advice is not None and advice.status == "pending"
    assert advice.suggested_price == pytest.approx(284.58)  # 279×1.02，与 README 手算一致
    payload = advice.payload
    assert len(payload["sample_quotes"]) == 3  # 可售证据：3 条可成交报价
    assert payload["excluded_quotes"] == []
    assert all(quote["availability"] == "in_stock" for quote in payload["sample_quotes"])


def test_unsellable_quotes_excluded_but_kept(db):
    _, _, snapshots = _catalog(db)
    # 前天报价临时缺货：快照保留，样本只剩 2 条可成交报价
    snapshots[0].availability = "out_of_stock"
    snapshots[0].stock = 0
    db.flush()
    run = _run_once(db)
    advice = _only_advice(db)
    assert advice is not None and advice.status == "pending"
    payload = advice.payload
    assert len(payload["sample_quotes"]) == 2
    assert len(payload["excluded_quotes"]) == 1
    excluded = payload["excluded_quotes"][0]
    assert excluded["availability"] == "out_of_stock"
    assert "缺货" in excluded["reason"] or "不可成交" in excluded["reason"]
    assert run.metrics["excluded_unsellable"] == 1
    # 缺货快照仍在库里（记录不丢）
    assert db.scalar(select(func.count()).select_from(Snapshot)) == 3


def test_rerun_same_calculation_adds_no_advices(db):
    _catalog(db)
    first = _run_once(db)
    second = _run_once(db)
    assert second.id == first.id  # 同一测算复用同一运行
    assert db.scalar(select(func.count()).select_from(Run)) == 1
    assert db.scalar(select(func.count()).select_from(Advice)) == 1
    advice = _only_advice(db)
    assert advice.status == "pending"
    assert advice.suggested_price == pytest.approx(284.58)


def test_availability_sync_stales_then_recovers(db):
    _, sku, snapshots = _catalog(db)
    run = _run_once(db)
    assert _only_advice(db).status == "pending"

    # 上游：三条报价全部临时缺货 → 窗口内无可成交报价 → 建议失效（记录保留）
    result = availability_service.apply_availability_updates(
        db,
        [
            {"snapshot_id": snapshot.id, "availability": "out_of_stock", "stock": 0, "note": "上游：临时缺货"}
            for snapshot in snapshots
        ],
    )
    assert result["changed_count"] == 3
    assert len(result["invalidated"]) == 1
    advice = _only_advice(db)
    assert advice.status == "stale"
    assert advice.stale_reason == pricing_service.STALE_NO_SELLABLE
    assert db.scalar(select(func.count()).select_from(Advice)) == 1  # 失效不删记录
    db.refresh(run)
    assert run.metrics["advices"] == 0 and run.metrics["stale"] == 1

    # 上游：恢复现货 → 同一条建议被同步算活，不新增建议
    result = availability_service.apply_availability_updates(
        db,
        [{"snapshot_id": snapshot.id, "availability": "in_stock", "stock": 8} for snapshot in snapshots],
    )
    assert len(result["refreshed"]) == 1
    advice = _only_advice(db)
    assert advice.status == "pending"
    assert advice.stale_reason is None
    assert advice.suggested_price == pytest.approx(284.58)
    assert db.scalar(select(func.count()).select_from(Advice)) == 1


def test_partial_oos_reprices_in_place(db):
    _, sku, snapshots = _catalog(db)
    _run_once(db)
    before = _only_advice(db)
    # 只有 1 条报价缺货：建议不失效，按剩下 2 条可成交报价原地重算
    result = availability_service.apply_availability_updates(
        db,
        [{"snapshot_id": snapshots[0].id, "availability": "delisted", "stock": 0, "note": "上游：链接下架"}],
    )
    assert len(result["refreshed"]) == 1
    assert result["invalidated"] == []
    advice = _only_advice(db)
    assert advice.id == before.id and advice.status == "pending"
    assert len(advice.payload["sample_quotes"]) == 2
    assert len(advice.payload["excluded_quotes"]) == 1
    assert db.scalar(select(func.count()).select_from(Advice)) == 1


def test_decided_advice_is_not_flipped_but_flagged(db):
    _, sku, snapshots = _catalog(db)
    _run_once(db)
    advice = _only_advice(db)
    advice.status = "approved"
    advice.approver = "admin@pricewatch.io"
    db.flush()
    availability_service.apply_availability_updates(
        db,
        [
            {"snapshot_id": snapshot.id, "availability": "out_of_stock", "stock": 0}
            for snapshot in snapshots
        ],
    )
    db.refresh(advice)
    assert advice.status == "approved"  # 审批结论不被覆盖
    assert advice.payload["basis_stale"] is True  # 但依据失效有标注
