"""运行记录服务：编号、序列化、列表/详情。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.competitor import Competitor
from src.models.run import Run
from src.utils.errors import not_found
from src.utils.timeutil import iso_utc, local_now


def serialize(run: Run, competitor_name: str | None = None) -> dict:
    return {
        "id": run.id,
        "run_no": run.run_no,
        "trigger": run.trigger,
        "status": run.status,
        "operator_email": run.operator_email,
        "captured_on": run.captured_on.isoformat() if run.captured_on else None,
        "competitor_id": run.competitor_id,
        "competitor_name": competitor_name,
        "input_count": run.input_count,
        "output_count": run.output_count,
        "metrics": run.metrics or {},
        "log_text": run.log_text,
        "started_at": iso_utc(run.started_at),
        "finished_at": iso_utc(run.finished_at),
    }


def next_run_no(db: Session) -> str:
    prefix = f"PW{local_now():%Y%m%d}"
    count = db.scalar(select(func.count()).select_from(Run).where(Run.run_no.like(f"{prefix}%"))) or 0
    return f"{prefix}-{count + 1:04d}"


def list_runs(db: Session, *, status: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    stmt = select(Run)
    count_stmt = select(func.count()).select_from(Run)
    if status:
        stmt = stmt.where(Run.status == status)
        count_stmt = count_stmt.where(Run.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.order_by(Run.id.desc()).limit(limit).offset(offset)).all()
    names = {row.id: row.name for row in db.scalars(select(Competitor)).all()}
    return {
        "items": [serialize(row, names.get(row.competitor_id)) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_run(db: Session, run_id: int) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise not_found("run", run_id)
    return run


def app_name() -> str:
    return settings.app_name
