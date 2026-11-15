"""幂等 seed：3 账号 / 6 竞品 / 320 SKU / 5 规则 / 960 快照 / 1 次测算（42 条建议）。

自然键 upsert：
  users.email
  competitors.code
  skus.sku_code
  rules.code
  snapshots(sku_id, captured_on)
  runs.seed_key
  advices(run_id, sku_id)
  audit_logs.seed_key

重复执行不新增、不覆盖审批状态；SEED_SUMMARY 逐字一致。
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select

from src.config.database import session_scope
from src.models.advice import Advice
from src.models.audit import AuditLog
from src.models.competitor import Competitor
from src.models.rule import Rule
from src.models.run import Run
from src.models.sku import Sku
from src.models.snapshot import Snapshot
from src.models.user import User
from src.services import effective_price, pricing_service
from src.utils.security import hash_password
from src.utils.timeutil import local_now, utcnow

from scripts.demo_config import (
    BRAND,
    CAPTURE_DAYS,
    DEMO_PASSWORD,
    DEMO_USERS,
    ORG,
    SHOWPIECE_CODE,
    build_dataset,
)


def ensure_users(db) -> int:
    for email, display_name, role in DEMO_USERS:
        if db.scalar(select(User).where(User.email == email)) is None:
            db.add(
                User(
                    email=email,
                    password_hash=hash_password(DEMO_PASSWORD),
                    display_name=display_name,
                    role=role,
                    org=ORG,
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(User)) or 0


def ensure_competitors(db, specs: list[dict]) -> dict[str, Competitor]:
    for spec in specs:
        competitor = db.scalar(select(Competitor).where(Competitor.code == spec["code"]))
        if competitor is None:
            competitor = Competitor(
                code=spec["code"],
                name=spec["name"],
                platform=spec["platform"],
                shop_url=spec.get("shop_url"),
                region=spec.get("region") or "华东",
                owner=ORG,
                note=spec.get("note"),
                capture_config=spec.get("capture_config") or {},
                enabled=True,
            )
            db.add(competitor)
            db.flush()
    return {row.code: row for row in db.scalars(select(Competitor)).all()}


def ensure_skus(db, specs: list[dict], competitors: dict[str, Competitor]) -> dict[str, Sku]:
    for spec in specs:
        sku = db.scalar(select(Sku).where(Sku.sku_code == spec["sku_code"]))
        if sku is None:
            competitor = competitors.get(spec["competitor_code"])
            if competitor is None:
                continue
            sku = Sku(
                sku_code=spec["sku_code"],
                name=spec["name"],
                category=spec["category"],
                competitor_id=competitor.id,
                competitor_item_id=spec["competitor_item_id"],
                unit=spec["unit"],
                cost=spec["cost"],
                floor_price=spec["floor_price"],
                target_margin_pct=spec["target_margin_pct"],
                current_price=spec["current_price"],
                stock=spec["stock"],
                note=spec.get("note") or None,
                enabled=True,
            )
            db.add(sku)
    db.flush()
    return {row.sku_code: row for row in db.scalars(select(Sku)).all()}


def ensure_rules(db, specs: list[dict], skus: dict[str, Sku]) -> int:
    for spec in specs:
        if db.scalar(select(Rule).where(Rule.code == spec["code"])) is None:
            scope_kind = spec["scope_kind"]
            sku_id = skus[spec["scope_value"]].id if scope_kind == "sku" and spec["scope_value"] in skus else None
            db.add(
                Rule(
                    code=spec["code"],
                    name=spec["name"],
                    scope_kind=scope_kind,
                    scope_value=spec["scope_value"],
                    sku_id=sku_id,
                    strategy=spec["strategy"],
                    target_margin_pct=spec["target_margin_pct"],
                    max_drop_pct=spec["max_drop_pct"],
                    priority=spec["priority"],
                    enabled=True,
                    note=spec.get("note"),
                )
            )
    db.flush()
    return db.scalar(select(func.count()).select_from(Rule)) or 0


def ensure_snapshots(db, specs: list[dict], skus: dict[str, Sku], competitors: dict[str, Competitor], today: date) -> int:
    existing = {
        (row.sku_id, row.captured_on)
        for row in db.execute(select(Snapshot.sku_id, Snapshot.captured_on)).all()
    }
    created = 0
    for spec in specs:
        sku = skus.get(spec["sku_code"])
        competitor = competitors.get(spec["competitor_code"])
        if sku is None or competitor is None:
            continue
        captured_on = today - timedelta(days=spec["captured_on_offset"])
        if (sku.id, captured_on) in existing:
            continue
        result = effective_price.compute_effective_price(spec["spec"])
        db.add(
            Snapshot(
                sku_id=sku.id,
                competitor_id=competitor.id,
                captured_on=captured_on,
                page_price=spec["page_price"],
                full_reduction=spec["full_reduction"],
                shop_coupon=spec["shop_coupon"],
                platform_coupon=spec["platform_coupon"],
                member_discount=spec["member_discount"],
                stock=spec["stock"],
                campaign=spec["campaign"],
                source_url=f"{competitor.shop_url}/item/{sku.competitor_item_id}" if competitor.shop_url else None,
                effective=result,
                seed_key=f"seed-snap-{sku.sku_code}-{spec['captured_on_offset']}",
            )
        )
        created += 1
        if created % 200 == 0:
            db.flush()
    db.flush()
    return db.scalar(select(func.count()).select_from(Snapshot)) or 0


def ensure_run(db, today: date) -> Run:
    return pricing_service.compute_run(
        db,
        captured_on=today,
        operator_email="admin@pricewatch.io",
        trigger="seed",
        seed_key="seed-run-capture-today",
    )


def ensure_audit(db) -> None:
    seeds = [
        ("seed-audit-1", "admin@pricewatch.io", "admin", "competitor.create", "competitor", {"code": "dy-muyan"}),
        ("seed-audit-2", "analyst@pricewatch.io", "analyst", "run.create", "run", {"run": "seed-run-capture-today"}),
    ]
    for seed_key, email, role, action, entity, detail in seeds:
        if db.scalar(select(AuditLog).where(AuditLog.seed_key == seed_key)) is None:
            db.add(
                AuditLog(
                    actor_email=email,
                    actor_role=role,
                    action=action,
                    entity=entity,
                    detail=detail,
                    layer="seed",
                    seed_key=seed_key,
                )
            )
    db.flush()


def seed_all() -> dict:
    dataset = build_dataset()
    today = local_now().date()
    with session_scope() as db:
        users = ensure_users(db)
        competitors = ensure_competitors(db, dataset["competitors"])
        skus = ensure_skus(db, dataset["skus"], competitors)
        ensure_rules(db, dataset["rules"], skus)
        ensure_snapshots(db, dataset["snapshots"], skus, competitors, today)
        run = ensure_run(db, today)
        ensure_audit(db)
        db.flush()

        sources = db.scalar(select(func.count()).select_from(Competitor)) or 0
        runs = db.scalar(select(func.count()).select_from(Run)) or 0
        findings = db.scalar(select(func.count()).select_from(Advice)) or 0
        pending = db.scalar(select(func.count()).select_from(Advice).where(Advice.status == "pending")) or 0
        summary = (
            f"SEED_SUMMARY brand={BRAND} users={users} sources={sources} "
            f"runs={runs} findings={findings} pending={pending}"
        )
        print(summary, flush=True)
        return {
            "users": users,
            "sources": sources,
            "runs": runs,
            "findings": findings,
            "pending": pending,
            "run_no": run.run_no,
            "snapshots": db.scalar(select(func.count()).select_from(Snapshot)) or 0,
            "skus": db.scalar(select(func.count()).select_from(Sku)) or 0,
            "rules": db.scalar(select(func.count()).select_from(Rule)) or 0,
            "days": CAPTURE_DAYS,
            "showpiece": SHOWPIECE_CODE,
            "captured_on": today.isoformat(),
            "seeded_at": utcnow().isoformat(timespec="seconds"),
        }


if __name__ == "__main__":
    seed_all()
