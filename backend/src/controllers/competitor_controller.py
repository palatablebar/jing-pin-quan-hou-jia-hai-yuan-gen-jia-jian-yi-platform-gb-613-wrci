"""竞品店铺控制器：写操作记领域审计。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, competitor_service


def list_competitors(db: Session, **filters) -> dict:
    return competitor_service.list_competitors(db, **filters)


def get_competitor(db: Session, competitor_id: int) -> dict:
    competitor = competitor_service.get_competitor(db, competitor_id)
    from src.models.sku import Sku

    count = len([sku for sku in db.query(Sku).filter(Sku.competitor_id == competitor.id).all()])
    return competitor_service.serialize(competitor, count)


def create_competitor(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    competitor = competitor_service.create_competitor(db, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="competitor.create",
        entity="competitor",
        entity_id=competitor.id,
        detail={"code": competitor.code, "platform": competitor.platform},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return competitor_service.serialize(competitor, 0)


def update_competitor(db: Session, competitor_id: int, payload: dict, principal: dict, request: Request) -> dict:
    competitor = competitor_service.get_competitor(db, competitor_id)
    competitor_service.update_competitor(db, competitor, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="competitor.update",
        entity="competitor",
        entity_id=competitor.id,
        detail={"fields": list(payload.keys())},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return competitor_service.serialize(competitor)
