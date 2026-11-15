"""Celery 任务：心跳 + 每日 08:40 自动测算（抓价快照回放 + 券后价还原 + 跟价建议）。"""
from __future__ import annotations

import time

from sqlalchemy import select

from src.config.celery_app import TASK_DAILY, TASK_HEARTBEAT, celery_app
from src.config.settings import settings
from src.utils.logger import get_logger

logger = get_logger("tasks")


def _redis():
    import redis

    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


@celery_app.task(name=TASK_HEARTBEAT)
def heartbeat() -> str:
    try:
        _redis().set(f"{settings.app_name}:worker:heartbeat", time.time())
        return "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("heartbeat failed: %s", exc)
        return "error"


@celery_app.task(name=TASK_DAILY)
def daily_pricing() -> dict:
    from src.config.database import session_scope
    from src.models.competitor import Competitor
    from src.services import audit_service, pricing_service
    from src.utils.timeutil import local_now

    today = local_now().date()
    with session_scope() as db:
        run = pricing_service.compute_run(
            db,
            captured_on=today,
            operator_email=f"scheduler@{settings.app_name}.io",
            trigger="schedule",
        )
        audit_service.record(
            db,
            actor_email=f"scheduler@{settings.app_name}.io",
            actor_role="admin",
            action="run.create",
            entity="run",
            entity_id=run.id,
            detail={"trigger": "schedule", "run_no": run.run_no, "advices": run.output_count},
            layer="worker",
        )
        competitors = db.scalar(select(Competitor).limit(1))
        logger.info("daily pricing finished: run=%s advices=%s", run.run_no, run.output_count)
        return {"run_no": run.run_no, "advices": run.output_count, "has_competitor": competitors is not None}
