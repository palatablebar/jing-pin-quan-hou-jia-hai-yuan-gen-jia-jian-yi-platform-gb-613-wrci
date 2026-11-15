from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.constants.roles import SKU_WRITE_ROLES
from src.controllers import snapshot_controller
from src.middlewares.rbac import READ_ROLES, require_roles
from src.schemas.snapshot import SnapshotIn
from src.utils.pagination import page_params

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


@router.get("")
def list_snapshots(
    captured_on: date | None = None,
    competitor_id: int | None = None,
    category: str | None = None,
    sku_id: int | None = None,
    q: str | None = None,
    limit: int = Query(40),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*READ_ROLES)),
) -> dict:
    page = page_params(limit, offset)
    return snapshot_controller.list_snapshots(
        db,
        captured_on=captured_on,
        competitor_id=competitor_id,
        category=category,
        sku_id=sku_id,
        q=q,
        role=principal["role"],
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{snapshot_id}")
def get_snapshot(
    snapshot_id: int, db: Session = Depends(get_db), principal: dict = Depends(require_roles(*READ_ROLES))
) -> dict:
    return snapshot_controller.get_snapshot(db, snapshot_id, principal["role"])


@router.post("", status_code=201)
def create_snapshot(
    payload: SnapshotIn,
    request: Request,
    db: Session = Depends(get_db),
    principal: dict = Depends(require_roles(*SKU_WRITE_ROLES)),
) -> dict:
    return snapshot_controller.create_snapshot(db, payload.model_dump(), principal, request)
