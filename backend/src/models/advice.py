"""跟价建议（原 Finding 实体）：算法 B 输出 + 审批结论。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Advice(Base):
    __tablename__ = "advices"
    __table_args__ = (UniqueConstraint("run_id", "sku_id", name="uq_advices_run_sku"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), index=True)
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("snapshots.id", ondelete="SET NULL"), nullable=True)
    competitor_id: Mapped[int | None] = mapped_column(ForeignKey("competitors.id", ondelete="SET NULL"), nullable=True)
    rule_code: Mapped[str] = mapped_column(String(40), default="")
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(String(16), default="follow", index=True)
    severity: Mapped[str] = mapped_column(String(12), default="low", index=True)  # 风险等级 high/medium/low
    score: Mapped[float] = mapped_column(Float, default=0.0)  # |gap_pct|
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    suggested_price: Mapped[float] = mapped_column(Float, default=0.0)
    effective_price: Mapped[float] = mapped_column(Float, default=0.0)  # 竞品券后单件价
    p10: Mapped[float] = mapped_column(Float, default=0.0)
    p25: Mapped[float] = mapped_column(Float, default=0.0)
    p50: Mapped[float] = mapped_column(Float, default=0.0)
    margin_pct: Mapped[float] = mapped_column(Float, default=0.0)
    gap_pct: Mapped[float] = mapped_column(Float, default=0.0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    approver: Mapped[str | None] = mapped_column(String(160), nullable=True)
    decide_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
