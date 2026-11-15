"""导出控制器：CSV 响应 + 审计。"""
from __future__ import annotations

from fastapi import Request, Response
from sqlalchemy.orm import Session

from src.services import audit_service, export_service
from src.utils.csv_export import csv_response_headers


def _respond(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type="text/csv; charset=utf-8", headers=csv_response_headers(filename))


def advices_csv(db: Session, run_id: int | None, principal: dict, request: Request) -> Response:
    content = export_service.advices_csv(db, run_id)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.advices",
        entity="advice",
        entity_id=run_id,
        detail={"bytes": len(content)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return _respond(content, "pricewatch-advices.csv")


def snapshots_csv(db: Session, captured_on, principal: dict, request: Request) -> Response:
    content = export_service.snapshots_csv(db, captured_on)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.snapshots",
        entity="snapshot",
        entity_id=None,
        detail={"bytes": len(content), "captured_on": captured_on.isoformat() if captured_on else None},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return _respond(content, "pricewatch-snapshots.csv")


def runs_csv(db: Session, principal: dict, request: Request) -> Response:
    content = export_service.runs_csv(db)
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="export.advices",
        entity="run",
        entity_id=None,
        detail={"bytes": len(content), "kind": "runs"},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return _respond(content, "pricewatch-runs.csv")
