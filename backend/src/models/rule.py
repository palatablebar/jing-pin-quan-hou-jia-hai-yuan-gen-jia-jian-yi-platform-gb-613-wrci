"""跟价规则：作用域（SKU / 类目 / 竞品 / 全局）+ 目标毛利 + 策略。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Rule(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    scope_kind: Mapped[str] = mapped_column(String(16), default="global", index=True)  # global|competitor|category|sku
    scope_value: Mapped[str] = mapped_column(String(64), default="")
    sku_id: Mapped[int | None] = mapped_column(ForeignKey("skus.id", ondelete="CASCADE"), nullable=True)
    competitor_id: Mapped[int | None] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), nullable=True)
    strategy: Mapped[str] = mapped_column(String(16), default="guarded")
    target_margin_pct: Mapped[float] = mapped_column(Float, default=15.0)
    max_drop_pct: Mapped[float] = mapped_column(Float, default=15.0)
    priority: Mapped[int] = mapped_column(Integer, default=100, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
