"""导出服务：跟价建议清单 / 券后价快照 CSV（两个算法的结果都进导出）。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import (
    ADVICE_ACTION_LABELS,
    ADVICE_STATUS_LABELS,
    CATEGORY_LABELS,
    RISK_LABELS,
    RUN_STATUS_LABELS,
    TRIGGER_LABELS,
)
from src.models.advice import Advice
from src.models.competitor import Competitor
from src.models.run import Run
from src.models.sku import Sku
from src.models.snapshot import Snapshot
from src.utils.csv_export import to_csv


def _coupon_text(snapshot_fields: dict) -> str:
    parts: list[str] = []
    for tier in snapshot_fields.get("full_reduction") or []:
        parts.append(f"满{tier.get('threshold'):g}减{tier.get('minus'):g}")
    shop = snapshot_fields.get("shop_coupon") or {}
    if shop:
        parts.append(f"店铺券满{shop.get('threshold'):g}减{shop.get('minus'):g}")
    platform = snapshot_fields.get("platform_coupon") or {}
    if platform:
        parts.append(f"平台每满{platform.get('per'):g}减{platform.get('minus'):g}")
    discount = snapshot_fields.get("member_discount") or 1.0
    if float(discount) < 1.0:
        parts.append(f"会员{float(discount) * 100:g}%折")
    return "＋".join(parts)


def advices_csv(db: Session, run_id: int | None = None) -> bytes:
    stmt = select(Advice)
    if run_id:
        stmt = stmt.where(Advice.run_id == run_id)
    advices = db.scalars(stmt.order_by(Advice.severity, Advice.id)).all()
    skus = {row.id: row for row in db.scalars(select(Sku)).all()}
    competitors = {row.id: row for row in db.scalars(select(Competitor)).all()}
    runs = {row.id: row for row in db.scalars(select(Run)).all()}
    headers = [
        "建议编号", "运行号", "SKU编码", "SKU名称", "类目", "竞品店铺",
        "页面价", "券后1件", "券后2件", "券后3件", "命中组合",
        "竞品P10", "竞品P25", "竞品P50", "我方当前价", "建议价", "价差%", "建议毛利%",
        "风险", "动作", "状态", "规则", "审批人", "审批备注", "生成时间",
    ]
    rows = []
    for advice in advices:
        sku = skus.get(advice.sku_id)
        competitor = competitors.get(advice.competitor_id)
        run = runs.get(advice.run_id)
        snapshot = (advice.payload or {}).get("snapshot") or {}
        effective = {
            "full_reduction": snapshot.get("full_reduction"),
            "shop_coupon": snapshot.get("shop_coupon"),
            "platform_coupon": snapshot.get("platform_coupon"),
            "member_discount": snapshot.get("member_discount"),
        }
        rows.append(
            [
                advice.id,
                run.run_no if run else "",
                sku.sku_code if sku else "",
                sku.name if sku else "",
                CATEGORY_LABELS.get(sku.category, sku.category) if sku else "",
                competitor.name if competitor else "",
                f"{snapshot.get('page_price', ''):.2f}" if snapshot.get("page_price") else "",
                f"{snapshot.get('unit_price_1'):.2f}" if snapshot.get("unit_price_1") else "",
                f"{snapshot.get('unit_price_2'):.2f}" if snapshot.get("unit_price_2") else "",
                f"{snapshot.get('unit_price_3'):.2f}" if snapshot.get("unit_price_3") else "",
                snapshot.get("note") or _coupon_text(effective),
                f"{advice.p10:.2f}",
                f"{advice.p25:.2f}",
                f"{advice.p50:.2f}",
                f"{advice.current_price:.2f}",
                f"{advice.suggested_price:.2f}",
                f"{advice.gap_pct:.2f}",
                f"{advice.margin_pct:.2f}",
                RISK_LABELS.get(advice.severity, advice.severity),
                ADVICE_ACTION_LABELS.get(advice.action, advice.action),
                ADVICE_STATUS_LABELS.get(advice.status, advice.status),
                advice.rule_code,
                advice.approver or "",
                advice.decide_note or "",
                advice.created_at.strftime("%Y-%m-%d %H:%M") if advice.created_at else "",
            ]
        )
    return to_csv(headers, rows)


def snapshots_csv(db: Session, captured_on=None) -> bytes:
    stmt = select(Snapshot)
    if captured_on:
        stmt = stmt.where(Snapshot.captured_on == captured_on)
    snapshots = db.scalars(stmt.order_by(Snapshot.captured_on.desc(), Snapshot.id)).all()
    skus = {row.id: row for row in db.scalars(select(Sku)).all()}
    competitors = {row.id: row for row in db.scalars(select(Competitor)).all()}
    headers = [
        "快照编号", "快照日期", "SKU编码", "SKU名称", "类目", "竞品店铺",
        "页面价", "满减", "店铺券", "平台券", "会员折扣",
        "券后1件", "券后2件", "券后3件", "最优件数", "命中组合", "券后折扣%", "采集活动",
    ]
    rows = []
    for snapshot in snapshots:
        sku = skus.get(snapshot.sku_id)
        competitor = competitors.get(snapshot.competitor_id)
        effective = snapshot.effective or {}
        rows.append(
            [
                snapshot.id,
                snapshot.captured_on.isoformat() if snapshot.captured_on else "",
                sku.sku_code if sku else "",
                sku.name if sku else "",
                CATEGORY_LABELS.get(sku.category, sku.category) if sku else "",
                competitor.name if competitor else "",
                f"{snapshot.page_price:.2f}",
                _coupon_text({"full_reduction": snapshot.full_reduction}),
                _coupon_text({"shop_coupon": snapshot.shop_coupon}),
                _coupon_text({"platform_coupon": snapshot.platform_coupon}),
                f"{snapshot.member_discount:g}",
                _fmt(effective.get("unit_price_1")),
                _fmt(effective.get("unit_price_2")),
                _fmt(effective.get("unit_price_3")),
                effective.get("best_units") or "",
                effective.get("note") or "",
                _fmt(effective.get("discount_pct")),
                snapshot.campaign,
            ]
        )
    return to_csv(headers, rows)


def _fmt(value) -> str:
    if value is None or value == "":
        return ""
    return f"{float(value):.2f}"


def runs_csv(db: Session) -> bytes:
    runs = db.scalars(select(Run).order_by(Run.id)).all()
    headers = ["运行号", "快照日期", "触发方式", "状态", "输入快照", "建议条数", "高风险", "平均价差%", "操作人", "开始时间", "结束时间"]
    rows = [
        [
            run.run_no,
            run.captured_on.isoformat() if run.captured_on else "",
            TRIGGER_LABELS.get(run.trigger, run.trigger),
            RUN_STATUS_LABELS.get(run.status, run.status),
            run.input_count,
            run.output_count,
            (run.metrics or {}).get("high", 0),
            (run.metrics or {}).get("avg_gap_pct", 0),
            run.operator_email,
            run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "",
            run.finished_at.strftime("%Y-%m-%d %H:%M") if run.finished_at else "",
        ]
        for run in runs
    ]
    return to_csv(headers, rows)
