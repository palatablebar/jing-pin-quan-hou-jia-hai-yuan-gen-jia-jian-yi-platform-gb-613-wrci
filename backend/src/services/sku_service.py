"""自有 SKU 服务：CRUD + 成本/底价脱敏。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.constants.enums import CATEGORY_LABELS
from src.constants.roles import cost_visible
from src.models.competitor import Competitor
from src.models.sku import Sku
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc


def serialize(sku: Sku, competitor: Competitor | None = None, role: str = "viewer") -> dict:
    visible = cost_visible(role)
    return {
        "id": sku.id,
        "sku_code": sku.sku_code,
        "name": sku.name,
        "category": sku.category,
        "category_label": CATEGORY_LABELS.get(sku.category, sku.category),
        "competitor_id": sku.competitor_id,
        "competitor_name": competitor.name if competitor else None,
        "competitor_code": competitor.code if competitor else None,
        "competitor_item_id": sku.competitor_item_id,
        "unit": sku.unit,
        "cost": round(sku.cost, 2) if visible else None,
        "floor_price": round(sku.floor_price, 2) if visible else None,
        "target_margin_pct": sku.target_margin_pct,
        "current_price": round(sku.current_price, 2),
        "stock": sku.stock,
        "note": sku.note,
        "enabled": sku.enabled,
        "cost_masked": not visible,
        "created_at": iso_utc(sku.created_at),
    }


def _competitor_map(db: Session) -> dict[int, Competitor]:
    return {row.id: row for row in db.scalars(select(Competitor)).all()}


def list_skus(
    db: Session,
    *,
    q: str | None = None,
    category: str | None = None,
    competitor_id: int | None = None,
    enabled: bool | None = None,
    role: str = "viewer",
    limit: int = 50,
    offset: int = 0,
) -> dict:
    stmt = select(Sku)
    count_stmt = select(func.count()).select_from(Sku)
    if q:
        like = f"%{q.strip()}%"
        condition = or_(Sku.name.ilike(like), Sku.sku_code.ilike(like), Sku.competitor_item_id.ilike(like))
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if category:
        stmt = stmt.where(Sku.category == category)
        count_stmt = count_stmt.where(Sku.category == category)
    if competitor_id:
        stmt = stmt.where(Sku.competitor_id == competitor_id)
        count_stmt = count_stmt.where(Sku.competitor_id == competitor_id)
    if enabled is not None:
        stmt = stmt.where(Sku.enabled == enabled)
        count_stmt = count_stmt.where(Sku.enabled == enabled)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Sku.id).limit(limit).offset(offset)).all()
    competitors = _competitor_map(db)
    return {
        "items": [serialize(row, competitors.get(row.competitor_id), role) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_sku(db: Session, sku_id: int) -> Sku:
    sku = db.get(Sku, sku_id)
    if sku is None:
        raise not_found("sku", sku_id)
    return sku


def serialize_detail(db: Session, sku: Sku, role: str) -> dict:
    from src.models.advice import Advice
    from src.models.snapshot import Snapshot
    from src.services import advice_service, snapshot_service

    competitor = db.get(Competitor, sku.competitor_id)
    data = serialize(sku, competitor, role)
    snapshot = db.scalar(
        select(Snapshot).where(Snapshot.sku_id == sku.id).order_by(Snapshot.captured_on.desc()).limit(1)
    )
    advice = db.scalar(select(Advice).where(Advice.sku_id == sku.id).order_by(Advice.id.desc()).limit(1))
    data["latest_snapshot"] = snapshot_service.serialize(db, snapshot, role) if snapshot else None
    data["latest_advice"] = advice_service.serialize(db, advice, role) if advice else None
    return data


def create_sku(db: Session, payload: dict) -> Sku:
    if db.scalar(select(Sku).where(Sku.sku_code == payload["sku_code"])) is not None:
        raise AppError("CONFLICT", 409, {"sku_code": payload["sku_code"]})
    competitor = db.get(Competitor, payload["competitor_id"])
    if competitor is None:
        raise AppError("NOT_FOUND", 404, {"entity": "competitor", "id": payload["competitor_id"]})
    _guard_prices(payload)
    sku = Sku(
        sku_code=payload["sku_code"],
        name=payload["name"],
        category=payload.get("category") or "sofa",
        competitor_id=payload["competitor_id"],
        competitor_item_id=payload.get("competitor_item_id") or "",
        unit=payload.get("unit") or "件",
        cost=float(payload.get("cost") or 0),
        floor_price=float(payload.get("floor_price") or 0),
        target_margin_pct=float(payload.get("target_margin_pct") or 15),
        current_price=float(payload.get("current_price") or 0),
        stock=int(payload.get("stock") or 0),
        note=payload.get("note"),
        enabled=payload.get("enabled", True),
    )
    db.add(sku)
    db.flush()
    return sku


def update_sku(db: Session, sku: Sku, payload: dict) -> Sku:
    merged = {
        "cost": payload.get("cost", sku.cost),
        "floor_price": payload.get("floor_price", sku.floor_price),
        "current_price": payload.get("current_price", sku.current_price),
        "target_margin_pct": payload.get("target_margin_pct", sku.target_margin_pct),
    }
    _guard_prices(merged)
    for field in (
        "name", "category", "competitor_item_id", "unit", "cost", "floor_price",
        "target_margin_pct", "current_price", "stock", "note", "enabled",
    ):
        if field in payload and payload[field] is not None:
            setattr(sku, field, payload[field])
    if "competitor_id" in payload and payload["competitor_id"]:
        if db.get(Competitor, payload["competitor_id"]) is None:
            raise AppError("NOT_FOUND", 404, {"entity": "competitor", "id": payload["competitor_id"]})
        sku.competitor_id = payload["competitor_id"]
    db.flush()
    return sku


def _guard_prices(payload: dict) -> None:
    cost = float(payload.get("cost") or 0)
    floor_price = float(payload.get("floor_price") or 0)
    current_price = float(payload.get("current_price") or 0)
    if current_price <= 0:
        raise AppError("VALIDATION", 422, {"field": "current_price", "reason": "当前价必须大于 0"})
    if cost > current_price:
        raise AppError("VALIDATION", 422, {"field": "cost", "reason": "成本不能高于当前价"})
    if floor_price < cost:
        raise AppError("VALIDATION", 422, {"field": "floor_price", "reason": "底价不能低于成本"})
    if floor_price > current_price:
        raise AppError("VALIDATION", 422, {"field": "floor_price", "reason": "底价不能高于当前价"})
