from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import SKU_WRITE_ROLES
from src.controllers import sku_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.sku import SkuIn, SkuPatch
from src.utils.pagination import page_params

router = APIRouter(prefix="/skus", tags=["skus"])


@router.get("")
def list_skus(
    q: str | None = None,
    category: str | None = None,
    competitor_id: int | None = None,
    enabled: bool | None = None,
    limit: int = Query(40),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return sku_controller.list_skus(
        db,
        q=q,
        category=category,
        competitor_id=competitor_id,
        enabled=enabled,
        role=principal["role"],
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{sku_id}")
def get_sku(
    sku_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return sku_controller.get_sku(db, sku_id, principal["role"])


@router.post("", status_code=201)
def create_sku(
    payload: SkuIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SKU_WRITE_ROLES)),
) -> dict:
    return sku_controller.create_sku(db, payload.model_dump(), principal, request)


@router.patch("/{sku_id}")
def update_sku(
    sku_id: int,
    payload: SkuPatch,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SKU_WRITE_ROLES)),
) -> dict:
    return sku_controller.update_sku(db, sku_id, payload.model_dump(exclude_unset=True), principal, request)
