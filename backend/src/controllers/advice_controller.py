"""跟价建议控制器：列表/详情/审批。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import advice_service, audit_service


def list_advices(db: Session, **filters) -> dict:
    role = filters.pop("role", "viewer")
    return advice_service.list_advices(db, role=role, **filters)


def get_advice(db: Session, advice_id: int, role: str) -> dict:
    return advice_service.serialize(db, advice_service.get_advice(db, advice_id), role)


def decide(db: Session, advice_id: int, payload: dict, principal: dict, request: Request) -> dict:
    advice = advice_service.get_advice(db, advice_id)
    advice_service.decide(
        db,
        advice,
        status=payload["status"],
        note=payload.get("note"),
        approver=principal["email"],
        approved_price=payload.get("approved_price"),
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="advice.decide",
        entity="advice",
        entity_id=advice.id,
        detail={"status": advice.status, "suggested_price": advice.suggested_price, "risk": advice.severity},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return advice_service.serialize(db, advice, principal["role"])
