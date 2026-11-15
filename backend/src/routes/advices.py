from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import DECIDE_ROLES
from src.controllers import advice_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.advice import DecisionIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/advices", tags=["advices"])


@router.get("")
def list_advices(
    status: str | None = None,
    risk: str | None = None,
    sku_id: int | None = None,
    run_id: int | None = None,
    q: str | None = None,
    limit: int = Query(40),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return advice_controller.list_advices(
        db,
        status=status,
        risk=risk,
        sku_id=sku_id,
        run_id=run_id,
        q=q,
        role=principal["role"],
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{advice_id}")
def get_advice(
    advice_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return advice_controller.get_advice(db, advice_id, principal["role"])


@router.patch("/{advice_id}/decision")
def decide(
    advice_id: int,
    payload: DecisionIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*DECIDE_ROLES)),
) -> dict:
    return advice_controller.decide(db, advice_id, payload.model_dump(), principal, request)
