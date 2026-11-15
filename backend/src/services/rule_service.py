"""跟价规则服务：按优先级匹配作用域（sku > category > competitor > global）。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.constants.enums import RULE_STRATEGY_LABELS
from src.models.competitor import Competitor
from src.models.rule import Rule
from src.models.sku import Sku
from src.utils.errors import AppError, not_found
from src.utils.timeutil import iso_utc

SCOPE_KINDS = ("global", "competitor", "category", "sku")


def serialize(rule: Rule) -> dict:
    return {
        "id": rule.id,
        "code": rule.code,
        "name": rule.name,
        "scope_kind": rule.scope_kind,
        "scope_value": rule.scope_value,
        "sku_id": rule.sku_id,
        "competitor_id": rule.competitor_id,
        "strategy": rule.strategy,
        "strategy_label": RULE_STRATEGY_LABELS.get(rule.strategy, rule.strategy),
        "target_margin_pct": rule.target_margin_pct,
        "max_drop_pct": rule.max_drop_pct,
        "priority": rule.priority,
        "enabled": rule.enabled,
        "note": rule.note,
        "created_at": iso_utc(rule.created_at),
    }


def list_rules(db: Session, *, enabled: bool | None = None, strategy: str | None = None) -> dict:
    stmt = select(Rule)
    if enabled is not None:
        stmt = stmt.where(Rule.enabled == enabled)
    if strategy:
        stmt = stmt.where(Rule.strategy == strategy)
    rows = db.scalars(stmt.order_by(Rule.priority, Rule.id)).all()
    return {"items": [serialize(row) for row in rows], "total": len(rows)}


def get_rule(db: Session, rule_id: int) -> Rule:
    rule = db.get(Rule, rule_id)
    if rule is None:
        raise not_found("rule", rule_id)
    return rule


def effective_rules(db: Session) -> list[Rule]:
    return list(db.scalars(select(Rule).where(Rule.enabled.is_(True)).order_by(Rule.priority, Rule.id)).all())


def match_rule(rules: list[Rule], sku: Sku, competitor_code: str | None) -> Rule:
    for rule in rules:
        if rule.scope_kind == "sku" and rule.sku_id == sku.id:
            return rule
    for rule in rules:
        if rule.scope_kind == "sku" and rule.scope_value and rule.scope_value == sku.sku_code:
            return rule
    for rule in rules:
        if rule.scope_kind == "category" and rule.scope_value == sku.category:
            return rule
    for rule in rules:
        if rule.scope_kind == "competitor" and rule.scope_value == competitor_code:
            return rule
    for rule in rules:
        if rule.scope_kind == "global":
            return rule
    raise AppError("VALIDATION", 422, {"reason": "没有可用的跟价规则"})


def create_rule(db: Session, payload: dict) -> Rule:
    if db.scalar(select(Rule).where(Rule.code == payload["code"])) is not None:
        raise AppError("CONFLICT", 409, {"code": payload["code"]})
    _guard_scope(db, payload)
    rule = Rule(
        code=payload["code"],
        name=payload["name"],
        scope_kind=payload.get("scope_kind") or "global",
        scope_value=payload.get("scope_value") or "",
        sku_id=payload.get("sku_id"),
        competitor_id=payload.get("competitor_id"),
        strategy=payload.get("strategy") or "guarded",
        target_margin_pct=float(payload.get("target_margin_pct") or 15),
        max_drop_pct=float(payload.get("max_drop_pct") or 15),
        priority=int(payload.get("priority") or 100),
        enabled=payload.get("enabled", True),
        note=payload.get("note"),
    )
    db.add(rule)
    db.flush()
    return rule


def update_rule(db: Session, rule: Rule, payload: dict) -> Rule:
    if "scope_kind" in payload and payload["scope_kind"]:
        _guard_scope(db, {**{"scope_kind": payload["scope_kind"]}, **payload})
    for field in (
        "name", "scope_kind", "scope_value", "sku_id", "competitor_id", "strategy",
        "target_margin_pct", "max_drop_pct", "priority", "enabled", "note",
    ):
        if field in payload and payload[field] is not None:
            setattr(rule, field, payload[field])
    db.flush()
    return rule


def _guard_scope(db: Session, payload: dict) -> None:
    scope_kind = payload.get("scope_kind") or "global"
    if scope_kind not in SCOPE_KINDS:
        raise AppError("VALIDATION", 422, {"field": "scope_kind"})
    if scope_kind == "sku" and not payload.get("sku_id") and not payload.get("scope_value"):
        raise AppError("VALIDATION", 422, {"field": "sku_id", "reason": "SKU 作用域需要 sku_id 或 sku_code"})
    if scope_kind == "competitor" and not payload.get("scope_value"):
        raise AppError("VALIDATION", 422, {"field": "scope_value", "reason": "竞品作用域需要竞品编码"})
    if scope_kind == "category" and not payload.get("scope_value"):
        raise AppError("VALIDATION", 422, {"field": "scope_value", "reason": "类目作用域需要类目编码"})
    margin = float(payload.get("target_margin_pct") or 0)
    if margin < 0 or margin > 200:
        raise AppError("VALIDATION", 422, {"field": "target_margin_pct"})
