"""自有 SKU：成本、底价、目标毛利、对标竞品店铺。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Sku(Base):
    __tablename__ = "skus"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sku_code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    category: Mapped[str] = mapped_column(String(20), default="sofa", index=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="RESTRICT"), index=True)
    competitor_item_id: Mapped[str] = mapped_column(String(64), default="")
    unit: Mapped[str] = mapped_column(String(16), default="件")
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    floor_price: Mapped[float] = mapped_column(Float, default=0.0)
    target_margin_pct: Mapped[float] = mapped_column(Float, default=15.0)
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
