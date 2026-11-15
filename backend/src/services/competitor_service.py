"""竞品店铺服务：CRUD + 序列化（含在架 SKU 数）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import PLATFORM_LABELS
from src.models.competitor import Competitor
from src.models.sku import Sku
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc


def serialize(competitor: Competitor, sku_count: int | None = None) -> dict:
    return {
        "id": competitor.id,
        "code": competitor.code,
        "name": competitor.name,
        "platform": competitor.platform,
        "platform_label": PLATFORM_LABELS.get(competitor.platform, competitor.platform),
        "shop_url": competitor.shop_url,
        "region": competitor.region,
        "owner": competitor.owner,
        "note": competitor.note,
        "capture_config": competitor.capture_config or {},
        "enabled": competitor.enabled,
        "sku_count": sku_count or 0,
        "last_captured_at": iso_utc(competitor.last_captured_at),
        "created_at": iso_utc(competitor.created_at),
    }


def _sku_counts(db: Session) -> dict[int, int]:
    rows = db.execute(select(Sku.competitor_id, func.count()).group_by(Sku.competitor_id)).all()
    return {competitor_id: count for competitor_id, count in rows}


def list_competitors(
    db: Session,
    *,
    q: str | None = None,
    platform: str | None = None,
    enabled: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    stmt = select(Competitor)
    count_stmt = select(func.count()).select_from(Competitor)
    if q:
        like = f"%{q.strip()}%"
        condition = Competitor.name.ilike(like) | Competitor.code.ilike(like)
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    if platform:
        stmt = stmt.where(Competitor.platform == platform)
        count_stmt = count_stmt.where(Competitor.platform == platform)
    if enabled is not None:
        stmt = stmt.where(Competitor.enabled == enabled)
        count_stmt = count_stmt.where(Competitor.enabled == enabled)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Competitor.id).limit(limit).offset(offset)).all()
    counts = _sku_counts(db)
    return {
        "items": [serialize(row, counts.get(row.id, 0)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_competitor(db: Session, competitor_id: int) -> Competitor:
    competitor = db.get(Competitor, competitor_id)
    if competitor is None:
        raise not_found("competitor", competitor_id)
    return competitor


def create_competitor(db: Session, payload: dict) -> Competitor:
    if db.scalar(select(Competitor).where(Competitor.code == payload["code"])) is not None:
        raise AppError("CONFLICT", 409, {"code": payload["code"]})
    competitor = Competitor(
        code=payload["code"],
        name=payload["name"],
        platform=payload.get("platform") or "taobao",
        shop_url=payload.get("shop_url"),
        region=payload.get("region") or "华东",
        owner=payload.get("owner") or "泊岸家居 · 电商定价组",
        note=payload.get("note"),
        capture_config=payload.get("capture_config") or {},
        enabled=payload.get("enabled", True),
    )
    db.add(competitor)
    db.flush()
    return competitor


def update_competitor(db: Session, competitor: Competitor, payload: dict) -> Competitor:
    for field in ("name", "platform", "shop_url", "region", "owner", "note", "capture_config", "enabled"):
        if field in payload and payload[field] is not None:
            setattr(competitor, field, payload[field])
    db.flush()
    return competitor
