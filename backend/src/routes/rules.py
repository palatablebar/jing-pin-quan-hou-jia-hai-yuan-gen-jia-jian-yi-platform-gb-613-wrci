from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import RULE_WRITE_ROLES
from src.controllers import rule_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.rule import RuleIn, RulePatch

router = APIRouter(prefix="/rules", tags=["rules"])


@router.get("")
def list_rules(
    enabled: bool | None = None,
    strategy: str | None = Query(default=None),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    return rule_controller.list_rules(db, enabled=enabled, strategy=strategy)


@router.post("", status_code=201)
def create_rule(
    payload: RuleIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*RULE_WRITE_ROLES)),
) -> dict:
    return rule_controller.create_rule(db, payload.model_dump(), principal, request)


@router.patch("/{rule_id}")
def update_rule(
    rule_id: int,
    payload: RulePatch,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*RULE_WRITE_ROLES)),
) -> dict:
    return rule_controller.update_rule(db, rule_id, payload.model_dump(exclude_unset=True), principal, request)
