"""抓价快照控制器：列表/详情/补录/上游可售状态同步。"""
from __future__ import annotations

from datetime import date

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.snapshot import Snapshot
from src.services import audit_service, availability_service, effective_price, snapshot_service
from src.utils.errors import AppError
from src.utils.timeutil import utcnow


def list_snapshots(db: Session, **filters) -> dict:
    data = snapshot_service.list_snapshots(db, **filters)
    data["capture_days"] = snapshot_service.capture_days(db)
    return data


def get_snapshot(db: Session, snapshot_id: int, role: str) -> dict:
    snapshot = snapshot_service.get_snapshot(db, snapshot_id)
    if not (snapshot.effective or {}).get("valid"):
        snapshot_service.recompute(db, snapshot)
        db.commit()
    return snapshot_service.serialize(db, snapshot, role, detail=True)


def create_snapshot(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    existing = db.scalar(
        select(Snapshot).where(Snapshot.sku_id == payload["sku_id"], Snapshot.captured_on == payload["captured_on"])
    )
    if existing is not None:
        raise AppError("CONFLICT", 409, {"sku_id": payload["sku_id"], "captured_on": str(payload["captured_on"])})
    from src.models.sku import Sku

    sku = db.get(Sku, payload["sku_id"])
    if sku is None:
        raise AppError("NOT_FOUND", 404, {"entity": "sku", "id": payload["sku_id"]})
    spec = {
        "page_price": payload["page_price"],
        "full_reduction": payload.get("full_reduction") or [],
        "shop_coupon": payload.get("shop_coupon"),
        "platform_coupon": payload.get("platform_coupon"),
        "member_discount": payload.get("member_discount", 1.0),
    }
    result = effective_price.compute_effective_price(spec)
    snapshot = Snapshot(
        sku_id=sku.id,
        competitor_id=sku.competitor_id,
        captured_on=payload["captured_on"],
        page_price=payload["page_price"],
        full_reduction=payload.get("full_reduction") or [],
        shop_coupon=payload.get("shop_coupon"),
        platform_coupon=payload.get("platform_coupon"),
        member_discount=payload.get("member_discount", 1.0),
        stock=payload.get("stock") or 0,
        availability=payload.get("availability") or "in_stock",
        availability_note=payload.get("availability_note"),
        availability_updated_at=utcnow() if payload.get("availability_note") else None,
        campaign=payload.get("campaign") or "手工补录",
        effective=result,
    )
    db.add(snapshot)
    db.flush()
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="snapshot.capture",
        entity="snapshot",
        entity_id=snapshot.id,
        detail={
            "sku_code": sku.sku_code,
            "captured_on": payload["captured_on"].isoformat() if isinstance(payload["captured_on"], date) else str(payload["captured_on"]),
            "unit_price_1": result.get("unit_price_1"),
            "valid": result.get("valid"),
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return snapshot_service.serialize(db, snapshot, principal["role"], detail=True)


def sync_availability(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    """上游库存可售状态同步：更新快照 → 相关建议失效并同步重算（原地更新，不新增）。"""
    result = availability_service.apply_availability_updates(db, payload.get("items") or [])
    snapshots = result.pop("snapshots")
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="snapshot.availability",
        entity="snapshot",
        entity_id=None,
        detail={
            "updated": result["updated_count"],
            "changed": result["changed_count"],
            "invalidated_advices": [item["advice_id"] for item in result["invalidated"]],
            "refreshed_advices": [item["advice_id"] for item in result["refreshed"]],
            "runs": result["runs"],
        },
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return {
        **result,
        "items": [snapshot_service.serialize(db, snapshot, principal["role"]) for snapshot in snapshots],
    }
