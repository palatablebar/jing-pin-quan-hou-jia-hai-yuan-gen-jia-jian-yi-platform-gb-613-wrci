from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

AvailabilityKind = Literal["in_stock", "out_of_stock", "delisted"]


class SnapshotIn(BaseModel):
    """手工补一条抓价快照（RPA 回放失败时补录），入库即做券后价还原。"""

    sku_id: int = Field(gt=0)
    captured_on: date
    page_price: float = Field(gt=0, le=1_000_000)
    full_reduction: list[dict] = Field(default_factory=list)
    shop_coupon: dict | None = None
    platform_coupon: dict | None = None
    member_discount: float = Field(default=1.0, ge=0.5, le=1.0)
    stock: int = Field(default=0, ge=0)
    availability: AvailabilityKind = "in_stock"
    availability_note: str | None = Field(default=None, max_length=255)
    campaign: str | None = Field(default=None, max_length=80)


class AvailabilityUpdateItem(BaseModel):
    """一条上游库存可售状态更新（按快照定位，报价记录保留不删除）。"""

    snapshot_id: int = Field(gt=0)
    availability: AvailabilityKind
    stock: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=255)


class AvailabilitySyncIn(BaseModel):
    """上游库存系统推送的一批可售状态更新；相关建议同步失效并重算。"""

    items: list[AvailabilityUpdateItem] = Field(min_length=1, max_length=200)


class RecomputeOut(BaseModel):
    id: int
    valid: bool
    note: str | None = None
