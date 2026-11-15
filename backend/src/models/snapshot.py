"""抓价快照：某天抓到的竞品页面价 + 活动/券配置 + 券后价还原结果（算法 A）。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (UniqueConstraint("sku_id", "captured_on", name="uq_snapshots_sku_day"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku_id: Mapped[int] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), index=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="RESTRICT"), index=True)
    captured_on: Mapped[date] = mapped_column(Date, index=True)
    page_price: Mapped[float] = mapped_column(Float, default=0.0)
    full_reduction: Mapped[list] = mapped_column(JSON, default=list)
    shop_coupon: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    platform_coupon: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    member_discount: Mapped[float] = mapped_column(Float, default=1.0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    campaign: Mapped[str] = mapped_column(String(80), default="")
    source_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 算法 A 输出：unit_price_1..3 / best / 命中组合说明
    effective: Mapped[dict] = mapped_column(JSON, default=dict)
    seed_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
