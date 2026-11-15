"""跟价建议服务：列表/详情/审批（审批仅 admin，来自路由依赖）。"""
from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from src.constants.enums import (
    ADVICE_ACTION_LABELS,
    ADVICE_STATUS_LABELS,
    CATEGORY_LABELS,
    RISK_LABELS,
    RiskLevel,
)
from src.constants.roles import cost_visible
from src.models.advice import Advice
from src.models.competitor import Competitor
from src.models.run import Run
from src.models.sku import Sku
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc, utcnow


def serialize(db: Session, advice: Advice, role: str = "viewer") -> dict:
    sku = db.get(Sku, advice.sku_id)
    competitor = db.get(Competitor, advice.competitor_id) if advice.competitor_id else None
    run = db.get(Run, advice.run_id)
    visible = cost_visible(role)
    payload = dict(advice.payload or {})
    if not visible:
        payload.pop("cost", None)
        payload.pop("floor_price", None)
        payload.pop("cost_floor", None)
    return {
        "id": advice.id,
        "run_id": advice.run_id,
        "run_no": run.run_no if run else None,
        "sku_id": advice.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "sku_name": sku.name if sku else None,
        "category": sku.category if sku else None,
        "category_label": CATEGORY_LABELS.get(sku.category, sku.category) if sku else None,
        "competitor_id": advice.competitor_id,
        "competitor_name": competitor.name if competitor else None,
        "competitor_code": competitor.code if competitor else None,
        "rule_code": advice.rule_code,
        "title": advice.title,
        "summary": advice.summary,
        "action": advice.action,
        "action_label": ADVICE_ACTION_LABELS.get(advice.action, advice.action),
        "severity": advice.severity,
        "severity_label": RISK_LABELS.get(advice.severity, advice.severity),
        "score": round(advice.score, 2),
        "status": advice.status,
        "status_label": ADVICE_STATUS_LABELS.get(advice.status, advice.status),
        "current_price": round(advice.current_price, 2),
        "suggested_price": round(advice.suggested_price, 2),
        "effective_price": round(advice.effective_price, 2),
        "p10": round(advice.p10, 2),
        "p25": round(advice.p25, 2),
        "p50": round(advice.p50, 2),
        "margin_pct": round(advice.margin_pct, 2),
        "gap_pct": round(advice.gap_pct, 2),
        "payload": payload,
        "approver": advice.approver,
        "decide_note": advice.decide_note,
        "decided_at": iso_utc(advice.decided_at),
        "created_at": iso_utc(advice.created_at),
    }


def list_advices(
    db: Session,
    *,
    status: str | None = None,
    risk: str | None = None,
    sku_id: int | None = None,
    run_id: int | None = None,
    q: str | None = None,
    role: str = "viewer",
    limit: int = 40,
    offset: int = 0,
) -> dict:
    stmt = select(Advice).join(Sku, Sku.id == Advice.sku_id)
    count_stmt = select(func.count()).select_from(Advice).join(Sku, Sku.id == Advice.sku_id)
    conditions = []
    if status:
        conditions.append(Advice.status == status)
    if risk:
        conditions.append(Advice.severity == risk)
    if sku_id:
        conditions.append(Advice.sku_id == sku_id)
    if run_id:
        conditions.append(Advice.run_id == run_id)
    if q:
        like = f"%{q.strip()}%"
        conditions.append(or_(Sku.name.ilike(like), Sku.sku_code.ilike(like), Advice.title.ilike(like)))
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total = db.scalar(count_stmt) or 0
    risk_rank = {RiskLevel.HIGH.value: 0, RiskLevel.MEDIUM.value: 1, RiskLevel.LOW.value: 2}
    rows = db.scalars(stmt.order_by(Advice.status, Advice.severity, Advice.id.desc()).limit(limit).offset(offset)).all()
    rows = sorted(rows, key=lambda row: (row.status != "pending", risk_rank.get(row.severity, 9), row.gap_pct))
    return {
        "items": [serialize(db, row, role) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_advice(db: Session, advice_id: int) -> Advice:
    advice = db.get(Advice, advice_id)
    if advice is None:
        raise not_found("advice", advice_id)
    return advice


def decide(db: Session, advice: Advice, *, status: str, note: str | None, approver: str, approved_price: float | None) -> Advice:
    if status not in ("approved", "rejected"):
        raise AppError("VALIDATION", 422, {"field": "status", "allowed": ["approved", "rejected"]})
    if status == "rejected" and not (note and note.strip()):
        raise AppError("VALIDATION", 422, {"field": "note", "reason": "驳回必须填写原因"})
    advice.status = status
    advice.decide_note = note
    advice.approver = approver
    advice.decided_at = utcnow()
    if approved_price is not None:
        if approved_price <= 0:
            raise AppError("VALIDATION", 422, {"field": "approved_price"})
        payload = dict(advice.payload or {})
        payload["approved_price"] = round(float(approved_price), 2)
        advice.payload = payload
        advice.suggested_price = round(float(approved_price), 2)
    advice.updated_at = utcnow()
    db.flush()
    return advice


def risk_counts(db: Session) -> dict[str, int]:
    rows = db.execute(select(Advice.severity, func.count()).group_by(Advice.severity)).all()
    return {key: count for key, count in rows}


def status_counts(db: Session) -> dict[str, int]:
    rows = db.execute(select(Advice.status, func.count()).group_by(Advice.status)).all()
    return {key: count for key, count in rows}
