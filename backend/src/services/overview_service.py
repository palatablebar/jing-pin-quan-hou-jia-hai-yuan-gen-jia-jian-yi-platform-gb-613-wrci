"""总览：待审批、风险结构、均价差、类目价差、最近运行、worker 心跳。"""
from __future__ import annotations

import time
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.constants.enums import (
    ADVICE_STATUS_LABELS,
    CATEGORY_LABELS,
    RISK_LABELS,
    RUN_STATUS_LABELS,
    RiskLevel,
)
from src.models.advice import Advice
from src.models.competitor import Competitor
from src.models.run import Run
from src.models.sku import Sku
from src.models.snapshot import Snapshot
from src.utils.timeutil import local_now, utcnow


def worker_alive() -> bool:
    try:
        import redis

        client = redis.Redis.from_url(settings.redis_url, decode_responses=True, socket_connect_timeout=2)
        value = client.get(f"{settings.app_name}:worker:heartbeat")
        return bool(value) and (time.time() - float(value)) < 120
    except Exception:
        return False


def overview(db: Session) -> dict:
    competitors_total = db.scalar(select(func.count()).select_from(Competitor)) or 0
    skus_total = db.scalar(select(func.count()).select_from(Sku)) or 0
    snapshots_total = db.scalar(select(func.count()).select_from(Snapshot)) or 0
    advices_total = db.scalar(select(func.count()).select_from(Advice)) or 0
    pending_total = db.scalar(select(func.count()).select_from(Advice).where(Advice.status == "pending")) or 0
    high_risk = (
        db.scalar(
            select(func.count()).select_from(Advice).where(Advice.severity == RiskLevel.HIGH.value, Advice.status == "pending")
        )
        or 0
    )

    gap_rows = db.execute(
        select(Advice.gap_pct, Advice.margin_pct, Advice.status).where(Advice.status == "pending")
    ).all()
    avg_gap = round(sum(float(row[0]) for row in gap_rows) / len(gap_rows), 2) if gap_rows else 0.0
    avg_margin = round(sum(float(row[1]) for row in gap_rows) / len(gap_rows), 2) if gap_rows else 0.0

    latest_day = db.scalar(select(func.max(Snapshot.captured_on)))
    discount_rows = []
    if latest_day:
        discount_rows = db.execute(
            select(Snapshot.effective).where(Snapshot.captured_on == latest_day)
        ).all()
    discounts = [
        float(row[0]["discount_pct"])
        for row in discount_rows
        if row[0] and row[0].get("discount_pct") is not None
    ]
    avg_discount = round(sum(discounts) / len(discounts), 2) if discounts else 0.0

    risk_rows = db.execute(
        select(Advice.severity, func.count()).where(Advice.status == "pending").group_by(Advice.severity)
    ).all()
    risk_map = {key: count for key, count in risk_rows}
    status_rows = db.execute(select(Advice.status, func.count()).group_by(Advice.status)).all()

    category_rows = db.execute(
        select(Sku.category, func.avg(Advice.gap_pct), func.count())
        .join(Sku, Sku.id == Advice.sku_id)
        .where(Advice.status == "pending")
        .group_by(Sku.category)
    ).all()
    category_gap = [
        {
            "key": key,
            "label": CATEGORY_LABELS.get(key, key),
            "avg_gap_pct": round(float(avg), 2),
            "count": count,
        }
        for key, avg, count in sorted(category_rows, key=lambda row: float(row[1]))
    ]

    top_rows = db.execute(
        select(Advice, Sku)
        .join(Sku, Sku.id == Advice.sku_id)
        .where(Advice.status == "pending")
        .order_by(Advice.severity, Advice.gap_pct)
        .limit(6)
    ).all()
    top_risk = [
        {
            "id": advice.id,
            "sku_code": sku.sku_code,
            "sku_name": sku.name,
            "category": sku.category,
            "category_label": CATEGORY_LABELS.get(sku.category, sku.category),
            "current_price": round(advice.current_price, 2),
            "suggested_price": round(advice.suggested_price, 2),
            "effective_price": round(advice.effective_price, 2),
            "gap_pct": round(advice.gap_pct, 2),
            "margin_pct": round(advice.margin_pct, 2),
            "risk": advice.severity,
            "risk_label": RISK_LABELS.get(advice.severity, advice.severity),
            "action": advice.action,
        }
        for advice, sku in top_rows
    ]

    latest_run = db.scalar(select(Run).order_by(Run.id.desc()).limit(1))
    since = utcnow() - timedelta(days=7)
    recent = db.scalars(select(Advice).where(Advice.created_at >= since)).all()
    today = local_now().date()
    trend = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = sum(
            1
            for advice in recent
            if advice.created_at
            and (advice.created_at + timedelta(minutes=settings.app_timezone_offset_minutes)).date() == day
        )
        trend.append({"date": day.isoformat(), "advices": count})

    return {
        "competitors_total": competitors_total,
        "skus_total": skus_total,
        "snapshots_total": snapshots_total,
        "advices_total": advices_total,
        "pending_total": pending_total,
        "high_risk_total": high_risk,
        "avg_gap_pct": avg_gap,
        "avg_margin_pct": avg_margin,
        "avg_discount_pct": avg_discount,
        "latest_capture_on": latest_day.isoformat() if isinstance(latest_day, date) else None,
        "worker_alive": worker_alive(),
        "risk": [
            {"key": key, "label": RISK_LABELS.get(key, key), "count": risk_map.get(key, 0)}
            for key in [RiskLevel.HIGH.value, RiskLevel.MEDIUM.value, RiskLevel.LOW.value]
        ],
        "status": [
            {"key": key, "label": ADVICE_STATUS_LABELS.get(key, key), "count": count}
            for key, count in sorted(status_rows)
        ],
        "category_gap": category_gap,
        "top_risk": top_risk,
        "trend": trend,
        "latest_run": {
            "id": latest_run.id,
            "run_no": latest_run.run_no,
            "status": latest_run.status,
            "status_label": RUN_STATUS_LABELS.get(latest_run.status, latest_run.status),
            "captured_on": latest_run.captured_on.isoformat() if latest_run.captured_on else None,
            "started_at": latest_run.started_at.isoformat(timespec="seconds") + "Z" if latest_run.started_at else None,
            "input_count": latest_run.input_count,
            "output_count": latest_run.output_count,
        }
        if latest_run
        else None,
    }
