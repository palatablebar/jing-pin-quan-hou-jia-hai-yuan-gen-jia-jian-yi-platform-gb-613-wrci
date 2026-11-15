"""抓价快照服务：入库时即做券后价还原（算法 A），列表/详情按角色脱敏。"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.constants.enums import CATEGORY_LABELS, PLATFORM_LABELS
from src.models.competitor import Competitor
from src.models.sku import Sku
from src.models.snapshot import Snapshot
from src.services import effective_price
from src.utils.errors import not_found
from src.utils.timeutil import iso_utc


def spec_of(snapshot: Snapshot) -> dict:
    return {
        "page_price": snapshot.page_price,
        "full_reduction": snapshot.full_reduction or [],
        "shop_coupon": snapshot.shop_coupon,
        "platform_coupon": snapshot.platform_coupon,
        "member_discount": snapshot.member_discount,
    }


def serialize(db: Session, snapshot: Snapshot, role: str = "viewer", *, detail: bool = False) -> dict:
    sku = db.get(Sku, snapshot.sku_id)
    competitor = db.get(Competitor, snapshot.competitor_id) if snapshot.competitor_id else None
    effective = snapshot.effective or {}
    data = {
        "id": snapshot.id,
        "sku_id": snapshot.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "sku_name": sku.name if sku else None,
        "category": sku.category if sku else None,
        "category_label": CATEGORY_LABELS.get(sku.category, sku.category) if sku else None,
        "competitor_id": snapshot.competitor_id,
        "competitor_name": competitor.name if competitor else None,
        "competitor_code": competitor.code if competitor else None,
        "platform_label": PLATFORM_LABELS.get(competitor.platform, competitor.platform) if competitor else None,
        "captured_on": snapshot.captured_on.isoformat() if snapshot.captured_on else None,
        "page_price": round(snapshot.page_price, 2),
        "full_reduction": snapshot.full_reduction or [],
        "shop_coupon": snapshot.shop_coupon,
        "platform_coupon": snapshot.platform_coupon,
        "member_discount": snapshot.member_discount,
        "stock": snapshot.stock,
        "campaign": snapshot.campaign,
        "source_url": snapshot.source_url,
        "unit_price_1": effective.get("unit_price_1"),
        "unit_price_2": effective.get("unit_price_2"),
        "unit_price_3": effective.get("unit_price_3"),
        "best_units": effective.get("best_units"),
        "best_unit_price": effective.get("best_unit_price"),
        "discount_pct": _discount_pct(snapshot, effective),
        "note": effective.get("note"),
        "valid": effective.get("valid", False),
        "warnings": effective.get("warnings") or [],
        "captured_at": iso_utc(snapshot.created_at),
    }
    if detail:
        data["effective"] = effective
        data["page_total_n2"] = round(snapshot.page_price * 2, 2)
        data["page_total_n3"] = round(snapshot.page_price * 3, 2)
    return data


def _discount_pct(snapshot: Snapshot, effective: dict) -> float:
    if effective.get("discount_pct") is not None:
        return round(float(effective["discount_pct"]), 2)
    unit1 = effective.get("unit_price_1")
    if not unit1 or not snapshot.page_price:
        return 0.0
    return round((1 - unit1 / snapshot.page_price) * 100, 2)


def list_snapshots(
    db: Session,
    *,
    captured_on: date | None = None,
    competitor_id: int | None = None,
    category: str | None = None,
    sku_id: int | None = None,
    q: str | None = None,
    role: str = "viewer",
    limit: int = 40,
    offset: int = 0,
) -> dict:
    stmt = select(Snapshot).join(Sku, Sku.id == Snapshot.sku_id)
    count_stmt = select(func.count()).select_from(Snapshot).join(Sku, Sku.id == Snapshot.sku_id)
    if captured_on:
        stmt = stmt.where(Snapshot.captured_on == captured_on)
        count_stmt = count_stmt.where(Snapshot.captured_on == captured_on)
    if competitor_id:
        stmt = stmt.where(Snapshot.competitor_id == competitor_id)
        count_stmt = count_stmt.where(Snapshot.competitor_id == competitor_id)
    if category:
        stmt = stmt.where(Sku.category == category)
        count_stmt = count_stmt.where(Sku.category == category)
    if sku_id:
        stmt = stmt.where(Snapshot.sku_id == sku_id)
        count_stmt = count_stmt.where(Snapshot.sku_id == sku_id)
    if q:
        like = f"%{q.strip()}%"
        condition = or_(Sku.name.ilike(like), Sku.sku_code.ilike(like))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Snapshot.captured_on.desc(), Snapshot.id.desc()).limit(limit).offset(offset)).all()
    return {
        "items": [serialize(db, row, role) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_snapshot(db: Session, snapshot_id: int) -> Snapshot:
    snapshot = db.get(Snapshot, snapshot_id)
    if snapshot is None:
        raise not_found("snapshot", snapshot_id)
    return snapshot


def capture_days(db: Session) -> list[str]:
    rows = db.execute(select(Snapshot.captured_on).distinct().order_by(Snapshot.captured_on.desc())).all()
    return [row[0].isoformat() for row in rows if row[0]]


def recompute(db: Session, snapshot: Snapshot) -> dict:
    result = effective_price.compute_effective_price(spec_of(snapshot))
    snapshot.effective = result
    return result
