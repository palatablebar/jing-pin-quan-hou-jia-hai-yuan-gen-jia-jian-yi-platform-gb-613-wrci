"""竞品店铺：定价组盯的 6 个竞品店铺（也是「接入源」的角色）。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base
from src.utils.timeutil import utcnow


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    platform: Mapped[str] = mapped_column(String(20), default="taobao", index=True)
    shop_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    region: Mapped[str] = mapped_column(String(40), default="华东")
    owner: Mapped[str] = mapped_column(String(80), default="泊岸家居 · 电商定价组")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    capture_config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
