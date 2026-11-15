"""测算运行控制器。"""
from __future__ import annotations

from datetime import date

from fastapi import Request
from sqlalchemy.orm import Session

from src.services import audit_service, pricing_service, run_service
from src.utils.errors import AppError
from src.utils.timeutil import local_now


def create_run(db: Session, payload: dict, principal: dict, request: Request) -> dict:
    captured_on = payload.get("captured_on") or local_now().date()
    if isinstance(captured_on, str):
        try:
            captured_on = date.fromisoformat(captured_on)
        except ValueError as exc:
            raise AppError("VALIDATION", 422, {"field": "captured_on"}) from exc
    if captured_on > local_now().date():
        raise AppError("VALIDATION", 422, {"field": "captured_on", "reason": "不能测算未来日期"})
    run = pricing_service.compute_run(
        db,
        captured_on=captured_on,
        operator_email=principal["email"],
        trigger=payload.get("trigger") or "manual",
        competitor_id=payload.get("competitor_id"),
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.create",
        entity="run",
        entity_id=run.id,
        detail={"run_no": run.run_no, "captured_on": run.captured_on.isoformat() if run.captured_on else None},
        ip=request.client.host if request.client else None,
    )
    audit_service.record(
        db,
        actor_email=principal["email"],
        actor_role=principal["role"],
        action="run.complete",
        entity="run",
        entity_id=run.id,
        detail={"status": run.status, "advices": run.output_count, "high": (run.metrics or {}).get("high", 0)},
        ip=request.client.host if request.client else None,
    )
    db.commit()
    return run_service.serialize(run)


def list_runs(db: Session, **filters) -> dict:
    return run_service.list_runs(db, **filters)


def get_run(db: Session, run_id: int) -> dict:
    return run_service.serialize(run_service.get_run(db, run_id))
