"""上游库存可售状态同步：更新快照可售状态 → 相关建议失效并同步重算（原地更新，不新增）。

口径：
  - 每次报价的可售状态逐条保留在快照上（缺货/下架快照不删除）；
  - 快照日期 D 的报价会影响 captured_on ∈ [D, D+2] 的测算窗口，相关建议即这些运行里
    该 SKU 的建议；
  - 同步在同一个事务里完成：快照更新 + 建议失效/重算 + 运行指标对齐 + 审计留痕。
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.constants.enums import AVAILABILITY_LABELS, Availability
from src.models.run import Run
from src.models.sku import Sku
from src.models.snapshot import Snapshot
from src.services import pricing_service
from src.utils.errors import AppError
from src.utils.timeutil import utcnow

VALID_AVAILABILITY = {item.value for item in Availability}


def _validate(item: dict, index: int) -> str:
    availability = item.get("availability")
    if availability not in VALID_AVAILABILITY:
        raise AppError(
            "VALIDATION",
            422,
            {"field": f"items[{index}].availability", "allowed": sorted(VALID_AVAILABILITY)},
        )
    return availability


def apply_availability_updates(db: Session, items: list[dict]) -> dict:
    """应用一批上游可售状态更新，同步失效/重算相关建议。返回同步结果摘要。"""
    changed: list[dict] = []
    snapshots: list[Snapshot] = []
    now = utcnow()
    for index, item in enumerate(items):
        availability = _validate(item, index)
        snapshot = db.get(Snapshot, item["snapshot_id"])
        if snapshot is None:
            raise AppError("NOT_FOUND", 404, {"entity": "snapshot", "id": item["snapshot_id"]})
        previous = snapshot.availability or Availability.IN_STOCK.value
        snapshot.availability = availability
        if item.get("stock") is not None:
            snapshot.stock = max(0, int(item["stock"]))
        if item.get("note") is not None:
            snapshot.availability_note = str(item["note"])[:255]
        snapshot.availability_updated_at = now
        snapshots.append(snapshot)
        if previous != availability:
            changed.append(
                {
                    "snapshot_id": snapshot.id,
                    "sku_id": snapshot.sku_id,
                    "captured_on": snapshot.captured_on,
                    "from": previous,
                    "to": availability,
                }
            )
    db.flush()

    # 受影响的 (sku, 快照日)：报价日 D 落在 captured_on ∈ [D, D+2] 的测算窗口里；
    # 同一 (运行, SKU) 只重算一次（多条报价同日变更不重复计）
    affected: dict[int, set] = {}
    for entry in changed:
        affected.setdefault(entry["sku_id"], set()).add(entry["captured_on"])

    pairs: set[tuple[int, int]] = set()  # (run_id, sku_id)
    run_ids: set[int] = set()
    for sku_id, days in affected.items():
        for day in sorted(days):
            rows = db.execute(
                select(Run.id).where(
                    Run.captured_on >= day,
                    Run.captured_on <= day + timedelta(days=pricing_service.CAPTURE_WINDOW_DAYS - 1),
                )
            ).all()
            for (run_id,) in rows:
                pairs.add((run_id, sku_id))
                run_ids.add(run_id)

    invalidated: list[dict] = []
    refreshed: list[dict] = []
    touched_runs: dict[int, Run] = {}
    skus = {row.id: row for row in db.scalars(select(Sku)).all()}
    runs = {row.id: row for row in db.scalars(select(Run).where(Run.id.in_(run_ids or {0}))).all()}
    for run_id, sku_id in sorted(pairs):
        sku = skus.get(sku_id)
        run = runs.get(run_id)
        if sku is None or run is None:
            continue
        advice, outcome = pricing_service.recompute_sku_advice(db, run, sku)
        if advice is None or outcome in ("absent", "untouched"):
            continue
        touched_runs[run.id] = run
        record = {
            "advice_id": advice.id,
            "run_id": run.id,
            "run_no": run.run_no,
            "sku_id": sku.id,
            "sku_code": sku.sku_code,
        }
        if outcome == "staled":
            invalidated.append({**record, "reason": advice.stale_reason})
        elif outcome == "refreshed":
            refreshed.append({**record, "suggested_price": round(advice.suggested_price, 2)})

    for run in touched_runs.values():
        pricing_service.refresh_run_metrics(
            db,
            run,
            note=(
                f"[可售同步] 上游库存状态更新，{len(invalidated)} 条建议失效、"
                f"{len(refreshed)} 条建议已按可成交报价重算。"
            ),
        )
    db.flush()
    return {
        "snapshots": snapshots,
        "updated_count": len(snapshots),
        "changed_count": len(changed),
        "changes": changed,
        "invalidated": invalidated,
        "refreshed": refreshed,
        "runs": [run.run_no for run in touched_runs.values()],
    }
