from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import COMPETITOR_WRITE_ROLES
from src.controllers import competitor_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.competitor import CompetitorIn, CompetitorPatch
from src.utils.pagination import page_params

router = APIRouter(prefix="/competitors", tags=["competitors"])


@router.get("")
def list_competitors(
    q: str | None = None,
    platform: str | None = None,
    enabled: bool | None = None,
    limit: int = Query(50),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return competitor_controller.list_competitors(
        db, q=q, platform=platform, enabled=enabled, limit=page.limit, offset=page.offset
    )


@router.get("/{competitor_id}")
def get_competitor(
    competitor_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return competitor_controller.get_competitor(db, competitor_id)


@router.post("", status_code=201)
def create_competitor(
    payload: CompetitorIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*COMPETITOR_WRITE_ROLES)),
) -> dict:
    return competitor_controller.create_competitor(db, payload.model_dump(), principal, request)


@router.patch("/{competitor_id}")
def update_competitor(
    competitor_id: int,
    payload: CompetitorPatch,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*COMPETITOR_WRITE_ROLES)),
) -> dict:
    return competitor_controller.update_competitor(
        db, competitor_id, payload.model_dump(exclude_unset=True), principal, request
    )
