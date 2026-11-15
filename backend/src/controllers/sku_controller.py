"""自有 SKU 控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, sku_service


def list_skus(db: Session, **filters) -> dict:
    return sku_service.list_skus(db, **filters)


def get_sku(db: Session, sku_id: int, role: str) -> dict:
    return sku_service.serialize_detail(db, sku_service.get_sku(db, sku_id), role)


def create_sku(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    sku = sku_service.create_sku(db, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="sku.create",
        entity="sku",
        entity_id=sku.id,
        detail={"sku_code": sku.sku_code, "current_price": sku.current_price},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return sku_service.serialize_detail(db, sku, principal["role"])


def update_sku(db: Session, sku_id: int, payload: dict, principal: dict, request: Request) -> dict:
    sku = sku_service.get_sku(db, sku_id)
    changes = {key: value for key, value in payload.items() if value is not None}
    sku_service.update_sku(db, sku, changes)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="sku.update",
        entity="sku",
        entity_id=sku.id,
        detail={"fields": list(changes.keys()), "current_price": sku.current_price, "floor_price": sku.floor_price},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return sku_service.serialize_detail(db, sku, principal["role"])
