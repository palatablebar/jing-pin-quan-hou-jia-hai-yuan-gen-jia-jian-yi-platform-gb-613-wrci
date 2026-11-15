"""测算主流程：抓价回放 → 算法 A（券后价还原）→ 算法 B（跟价建议）→ 建议入库。

纯服务端计算，同样的快照与规则两次运行结果一致；不访问外网。

可售口径（缺货/下架不压价）：
  - 每条快照自带 availability（in_stock / out_of_stock / delisted），逐条保留；
  - 算法 B 的近 3 天样本只取「当前仍能成交」的报价（in_stock 且券后价还原成功）；
  - 缺货/下架报价进入 excluded_quotes（带排除原因），快照与建议记录都不删除；
  - 同一测算（同快照日 + 同竞品范围）重跑复用原运行，建议原地刷新，不新增；
    不再成立的建议标记 stale（失效）而不是删除。
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import AVAILABILITY_LABELS, Availability
from src.models.advice import Advice
from src.models.competitor import Competitor
from src.models.rule import Rule
from src.models.run import Run
from src.models.sku import Sku
from src.models.snapshot import Snapshot
from src.services import advice_service, effective_price, follow_advice, rule_service, run_service
from src.utils.timeutil import utcnow

CAPTURE_WINDOW_DAYS = 3

# 失效原因（stale_reason / payload.stale_reason 的固定文案，页面与导出按此核对）
STALE_NO_SELLABLE = "竞品近 3 天没有可成交报价（缺货/下架或快照非法），建议失效"
STALE_NO_FOLLOW = "重算后价差在跟价阈值内，无需跟价，建议失效"
STALE_COMPUTE_FAILED = "跟价测算失败（价格口径非法），建议失效"


def _load_window(db: Session, captured_on: date) -> list[Snapshot]:
    start = captured_on - timedelta(days=CAPTURE_WINDOW_DAYS - 1)
    return list(
        db.scalars(
            select(Snapshot)
            .where(Snapshot.captured_on >= start, Snapshot.captured_on <= captured_on)
            .order_by(Snapshot.captured_on, Snapshot.id)
        ).all()
    )


def collect_sellable_quotes(window: list[Snapshot]) -> dict[int, dict]:
    """把窗口内的快照按 SKU 分成「可售样本」与「排除清单」（带排除原因）。

    纯函数：只读快照字段，不写库。缺货/下架的快照保留在 excluded 里，
    供建议 payload、页面与导出核对「这条报价为什么没进样本」。
    """
    grouped: dict[int, dict] = {}
    for snapshot in window:
        effective = snapshot.effective or {}
        availability = snapshot.availability or Availability.IN_STOCK.value
        quote = {
            "snapshot_id": snapshot.id,
            "captured_on": snapshot.captured_on.isoformat() if snapshot.captured_on else None,
            "page_price": round(snapshot.page_price, 2),
            "unit_price_1": effective.get("unit_price_1"),
            "availability": availability,
            "availability_label": AVAILABILITY_LABELS.get(availability, availability),
            "stock": snapshot.stock,
            "source_url": snapshot.source_url,
        }
        bucket = grouped.setdefault(snapshot.sku_id, {"sellable": [], "excluded": []})
        if not effective.get("valid"):
            quote["kind"] = "invalid"
            quote["reason"] = "券后价还原失败，不计入跟价样本"
            bucket["excluded"].append(quote)
        elif availability != Availability.IN_STOCK.value:
            quote["kind"] = "unsellable"
            quote["reason"] = f"{quote['availability_label']}，当前不可成交，不计入跟价样本"
            bucket["excluded"].append(quote)
        else:
            quote["kind"] = "sellable"
            quote["reason"] = ""
            bucket["sellable"].append(quote)
    return grouped


def _quote_evidence(group: dict) -> dict:
    """建议 payload 里的样本证据：可售样本（可售证据）+ 排除清单（排除原因）。"""
    return {
        "sample_quotes": group.get("sellable", []),
        "excluded_quotes": group.get("excluded", []),
    }


def _upsert_advice(
    db: Session,
    run: Run,
    existing: dict[int, Advice],
    sku: Sku,
    snapshot: Snapshot,
    result: dict,
    evidence: dict | None = None,
) -> Advice:
    advice = existing.get(sku.id)
    evidence = evidence or {"sample_quotes": [], "excluded_quotes": []}
    payload = {
        "algorithm": "B.follow_advice",
        "effective_algorithm": "A.effective_price",
        "current_price": round(sku.current_price, 2),
        "cost": round(sku.cost, 2),
        "floor_price": round(sku.floor_price, 2),
        "target_margin_pct": sku.target_margin_pct,
        "rule": result["strategy"],
        "cost_floor": result["cost_floor"],
        "market_cap": result["market_cap"],
        "clamped_by": result["clamped_by"],
        "breach": result["breach"],
        "reasons": result["reasons"],
        "p10": result["p10"],
        "p25": result["p25"],
        "p50": result["p50"],
        "mean": result["mean"],
        "samples": result["samples"],
        "sample_quotes": evidence["sample_quotes"],
        "excluded_quotes": evidence["excluded_quotes"],
        "snapshot": {
            "id": snapshot.id,
            "captured_on": snapshot.captured_on.isoformat(),
            "page_price": round(snapshot.page_price, 2),
            "full_reduction": snapshot.full_reduction or [],
            "shop_coupon": snapshot.shop_coupon,
            "platform_coupon": snapshot.platform_coupon,
            "member_discount": snapshot.member_discount,
            "availability": snapshot.availability or Availability.IN_STOCK.value,
            "availability_label": AVAILABILITY_LABELS.get(
                snapshot.availability or Availability.IN_STOCK.value, snapshot.availability
            ),
            "stock": snapshot.stock,
            "unit_price_1": (snapshot.effective or {}).get("unit_price_1"),
            "unit_price_2": (snapshot.effective or {}).get("unit_price_2"),
            "unit_price_3": (snapshot.effective or {}).get("unit_price_3"),
            "best_units": (snapshot.effective or {}).get("best_units"),
            "note": (snapshot.effective or {}).get("note"),
        },
    }
    title = f"{sku.name}：竞品券后 ¥{result['p25']:.2f} → 建议 ¥{result['suggested_price']:.2f}"
    summary = result["reason"]
    if advice is None:
        advice = Advice(
            run_id=run.id,
            sku_id=sku.id,
            snapshot_id=snapshot.id,
            competitor_id=sku.competitor_id,
            rule_code=result["rule_code"],
            title=title[:200],
            summary=summary,
            action=result["action"],
            severity=result["risk"],
            score=abs(result["gap_pct"]),
            status="pending",
            current_price=sku.current_price,
            suggested_price=result["suggested_price"],
            effective_price=result["p25"],
            p10=result["p10"],
            p25=result["p25"],
            p50=result["p50"],
            margin_pct=result["margin_pct"],
            gap_pct=result["gap_pct"],
            payload=payload,
        )
        db.add(advice)
    else:
        # 重算刷新数值，但绝不覆盖审批状态与审批意见；失效建议被重新算活则回到待审批
        if advice.status == "stale":
            advice.status = "pending"
        advice.stale_reason = None
        advice.snapshot_id = snapshot.id
        advice.competitor_id = sku.competitor_id
        advice.rule_code = result["rule_code"]
        advice.title = title[:200]
        advice.summary = summary
        advice.action = result["action"]
        advice.severity = result["risk"]
        advice.score = abs(result["gap_pct"])
        advice.current_price = sku.current_price
        advice.suggested_price = result["suggested_price"]
        advice.effective_price = result["p25"]
        advice.p10 = result["p10"]
        advice.p25 = result["p25"]
        advice.p50 = result["p50"]
        advice.margin_pct = result["margin_pct"]
        advice.gap_pct = result["gap_pct"]
        advice.payload = payload
    db.flush()
    return advice


def _mark_stale(advice: Advice, reason: str, evidence: dict | None = None) -> bool:
    """把建议标记为失效（记录保留，不删除）。已审批/已驳回的不翻状态，只在 payload 标注依据失效。"""
    payload = dict(advice.payload or {})
    payload["basis_stale"] = True
    payload["basis_stale_reason"] = reason
    if evidence:
        payload["sample_quotes"] = evidence.get("sample_quotes", [])
        payload["excluded_quotes"] = evidence.get("excluded_quotes", [])
    advice.payload = payload
    if advice.status in ("approved", "rejected"):
        return False
    advice.status = "stale"
    advice.stale_reason = reason
    advice.updated_at = utcnow()
    return True


def execute(db: Session, run: Run, captured_on: date, competitor_filter: int | None = None) -> dict:
    """执行一次测算，写入 run.metrics / run.log_text，返回 {metrics, log, status}。"""
    window = _load_window(db, captured_on)
    skus = {row.id: row for row in db.scalars(select(Sku)).all()}
    competitors = {row.id: row for row in db.scalars(select(Competitor)).all()}
    rules = rule_service.effective_rules(db)

    # 算法 A：窗口内每条快照都重算券后价（缺货/下架快照同样保留还原结果）
    for snapshot in window:
        snapshot.effective = effective_price.compute_effective_price(
            {
                "page_price": snapshot.page_price,
                "full_reduction": snapshot.full_reduction or [],
                "shop_coupon": snapshot.shop_coupon,
                "platform_coupon": snapshot.platform_coupon,
                "member_discount": snapshot.member_discount,
            }
        )
    groups = collect_sellable_quotes(window)
    invalid = sum(1 for group in groups.values() for quote in group["excluded"] if quote["kind"] == "invalid")
    unsellable = sum(1 for group in groups.values() for quote in group["excluded"] if quote["kind"] == "unsellable")

    targets = [
        snapshot
        for snapshot in window
        if snapshot.captured_on == captured_on
        and skus.get(snapshot.sku_id) is not None
        and skus[snapshot.sku_id].enabled
        and (competitor_filter is None or snapshot.competitor_id == competitor_filter)
    ]

    existing = {
        row.sku_id: row
        for row in db.scalars(select(Advice).where(Advice.run_id == run.id)).all()
    }
    advice_count = 0
    staled_count = 0
    risk_bucket = {"high": 0, "medium": 0, "low": 0}
    gaps: list[float] = []
    discounts: list[float] = []
    for snapshot in targets:
        sku = skus[snapshot.sku_id]
        competitor = competitors.get(snapshot.competitor_id)
        rule = rule_service.match_rule(rules, sku, competitor.code if competitor else None)
        group = groups.get(sku.id, {"sellable": [], "excluded": []})
        evidence = _quote_evidence(group)
        prices = [quote["unit_price_1"] for quote in group["sellable"]]
        advice = existing.get(sku.id)
        if not prices:
            # 窗口内没有可成交报价：旧建议失效（保留记录），不再出新建议
            if advice is not None and _mark_stale(advice, STALE_NO_SELLABLE, evidence):
                staled_count += 1
            continue
        try:
            result = follow_advice.build_advice(
                competitor_prices=prices,
                cost=sku.cost,
                floor_price=sku.floor_price,
                target_margin_pct=rule.target_margin_pct,
                current_price=sku.current_price,
                strategy=rule.strategy,
                max_drop_pct=rule.max_drop_pct,
            )
        except ValueError:
            invalid += 1
            if advice is not None and _mark_stale(advice, STALE_COMPUTE_FAILED, evidence):
                staled_count += 1
            continue
        result["rule_code"] = rule.code
        if (snapshot.effective or {}).get("discount_pct"):
            discounts.append(float(snapshot.effective["discount_pct"]))
        if not result["need_follow"]:
            if advice is not None and _mark_stale(advice, STALE_NO_FOLLOW, evidence):
                staled_count += 1
            continue
        _upsert_advice(db, run, existing, sku, snapshot, result, evidence)
        advice_count += 1
        risk_bucket[result["risk"]] = risk_bucket.get(result["risk"], 0) + 1
        gaps.append(result["gap_pct"])

    captured_at = utcnow()
    for competitor_id in {snapshot.competitor_id for snapshot in targets}:
        competitor = competitors.get(competitor_id)
        if competitor is not None:
            competitor.last_captured_at = captured_at

    metrics = {
        "window_snapshots": len(window),
        "snapshots": len(targets),
        "skus": len({snapshot.sku_id for snapshot in targets}),
        "advices": advice_count,
        "staled": staled_count,
        "high": risk_bucket.get("high", 0),
        "medium": risk_bucket.get("medium", 0),
        "low": risk_bucket.get("low", 0),
        "avg_gap_pct": round(sum(gaps) / len(gaps), 2) if gaps else 0.0,
        "avg_discount_pct": round(sum(discounts) / len(discounts), 2) if discounts else 0.0,
        "invalid_snapshots": invalid,
        "excluded_unsellable": unsellable,
        "rules_applied": len({rule.code for rule in rules}),
        "window_days": CAPTURE_WINDOW_DAYS,
        "captured_on": captured_on.isoformat(),
    }
    log = (
        f"[{captured_on.isoformat()}] 回放窗口 {CAPTURE_WINDOW_DAYS} 天，快照 {len(window)} 条；"
        f"当日待测算 {len(targets)} 条 SKU；券后价还原失败 {invalid} 条；"
        f"缺货/下架报价 {unsellable} 条已排除出跟价样本；"
        f"生成跟价建议 {advice_count} 条（高 {risk_bucket.get('high', 0)} / 中 {risk_bucket.get('medium', 0)} / 低 {risk_bucket.get('low', 0)}），"
        f"失效 {staled_count} 条；"
        f"平均价差 {metrics['avg_gap_pct']}%，平均券后折扣 {metrics['avg_discount_pct']}%。"
    )
    status = "success" if metrics["snapshots"] > 0 else "partial"
    if invalid and invalid >= max(1, metrics["snapshots"] // 2):
        status = "partial"
    return {"metrics": metrics, "log": log, "status": status}


def _find_reusable_run(db: Session, captured_on: date, competitor_id: int | None) -> Run | None:
    """同一测算（同快照日 + 同竞品范围）复用同一条运行：重跑原地刷新，不新增建议。"""
    return db.scalar(
        select(Run)
        .where(Run.captured_on == captured_on, Run.competitor_id == competitor_id)
        .order_by(Run.id)
        .limit(1)
    )


def compute_run(
    db: Session,
    *,
    captured_on: date,
    operator_email: str,
    trigger: str = "manual",
    seed_key: str | None = None,
    competitor_id: int | None = None,
) -> Run:
    if seed_key:
        existing = db.scalar(select(Run).where(Run.seed_key == seed_key))
        if existing is not None:
            return existing
        # 同日已有手工/定时测算：认领为种子运行，保证同一测算只有一条运行
        reusable = _find_reusable_run(db, captured_on, competitor_id)
        if reusable is not None:
            reusable.seed_key = seed_key
            db.flush()
            return reusable
    run = None if seed_key else _find_reusable_run(db, captured_on, competitor_id)
    if run is None:
        run = Run(
            run_no=run_service.next_run_no(db),
            trigger=trigger,
            status="running",
            operator_email=operator_email,
            captured_on=captured_on,
            competitor_id=competitor_id,
            seed_key=seed_key,
        )
        db.add(run)
    else:
        # 重跑同一测算：复用运行号，建议按 (run_id, sku_id) 原地刷新
        run.trigger = trigger
        run.operator_email = operator_email
        run.status = "running"
    db.flush()
    try:
        result = execute(db, run, captured_on, competitor_id)
        run.metrics = result["metrics"]
        run.log_text = result["log"]
        run.status = result["status"]
        run.input_count = result["metrics"]["snapshots"]
        run.output_count = result["metrics"]["advices"]
    except Exception as exc:  # noqa: BLE001 - 失败留痕，不抛 500
        run.status = "failed"
        run.log_text = f"测算失败：{exc}"
        run.metrics = {"error": str(exc)[:300]}
    run.finished_at = utcnow()
    db.flush()
    return run


def refresh_run_metrics(db: Session, run: Run, note: str | None = None) -> None:
    """可售状态同步后重算运行指标（建议已原地失效/刷新，指标跟着对齐）。"""
    advices = list(db.scalars(select(Advice).where(Advice.run_id == run.id)).all())
    active = [advice for advice in advices if advice.status != "stale"]
    stale = [advice for advice in advices if advice.status == "stale"]
    metrics = dict(run.metrics or {})
    metrics["advices"] = len(active)
    metrics["stale"] = len(stale)
    for level in ("high", "medium", "low"):
        metrics[level] = sum(1 for advice in active if advice.severity == level)
    gaps = [float(advice.gap_pct) for advice in active]
    metrics["avg_gap_pct"] = round(sum(gaps) / len(gaps), 2) if gaps else 0.0
    run.metrics = metrics
    run.output_count = len(active)
    if note:
        run.log_text = f"{run.log_text or ''}\n{note}".strip()
    db.flush()


def recompute_sku_advice(db: Session, run: Run, sku: Sku) -> tuple[Advice | None, str]:
    """对单个 SKU 在指定运行里同步重算建议（可售状态变化后调用）。

    返回 (advice, outcome)：outcome ∈ refreshed / staled / untouched / absent。
    只刷新或失效已有建议，不为该运行新增建议。
    """
    advice = db.scalar(select(Advice).where(Advice.run_id == run.id, Advice.sku_id == sku.id))
    if advice is None:
        return None, "absent"
    window = _load_window(db, run.captured_on)
    groups = collect_sellable_quotes(window)
    group = groups.get(sku.id, {"sellable": [], "excluded": []})
    evidence = _quote_evidence(group)
    prices = [quote["unit_price_1"] for quote in group["sellable"]]
    if not prices:
        changed = _mark_stale(advice, STALE_NO_SELLABLE, evidence)
        db.flush()
        return advice, "staled" if changed else "untouched"
    competitor = db.get(Competitor, sku.competitor_id)
    rules = rule_service.effective_rules(db)
    rule = rule_service.match_rule(rules, sku, competitor.code if competitor else None)
    try:
        result = follow_advice.build_advice(
            competitor_prices=prices,
            cost=sku.cost,
            floor_price=sku.floor_price,
            target_margin_pct=rule.target_margin_pct,
            current_price=sku.current_price,
            strategy=rule.strategy,
            max_drop_pct=rule.max_drop_pct,
        )
    except ValueError:
        changed = _mark_stale(advice, STALE_COMPUTE_FAILED, evidence)
        db.flush()
        return advice, "staled" if changed else "untouched"
    if not result["need_follow"]:
        changed = _mark_stale(advice, STALE_NO_FOLLOW, evidence)
        db.flush()
        return advice, "staled" if changed else "untouched"
    result["rule_code"] = rule.code
    snapshot = db.scalar(
        select(Snapshot)
        .where(Snapshot.sku_id == sku.id, Snapshot.captured_on == run.captured_on)
        .limit(1)
    )
    if snapshot is None:
        snapshot = db.get(Snapshot, advice.snapshot_id) if advice.snapshot_id else None
    if snapshot is None:
        return advice, "untouched"
    _upsert_advice(db, run, {sku.id: advice}, sku, snapshot, result, evidence)
    return advice, "refreshed"
