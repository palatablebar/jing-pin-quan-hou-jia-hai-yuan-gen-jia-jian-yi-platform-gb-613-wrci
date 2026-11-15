"""跟价规则控制器。"""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, rule_service


def list_rules(db: Session, **filters) -> dict:
    return rule_service.list_rules(db, **filters)


def create_rule(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    rule = rule_service.create_rule(db, payload)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="rule.create",
        entity="rule",
        entity_id=rule.id,
        detail={"code": rule.code, "strategy": rule.strategy, "target_margin_pct": rule.target_margin_pct},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return rule_service.serialize(rule)


def update_rule(db: Session, rule_id: int, payload: dict, principal: dict, request: Request) -> dict:
    rule = rule_service.get_rule(db, rule_id)
    changes = {key: value for key, value in payload.items() if value is not None}
    rule_service.update_rule(db, rule, changes)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="rule.update",
        entity="rule",
        entity_id=rule.id,
        detail={"fields": list(changes.keys())},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return rule_service.serialize(rule)
