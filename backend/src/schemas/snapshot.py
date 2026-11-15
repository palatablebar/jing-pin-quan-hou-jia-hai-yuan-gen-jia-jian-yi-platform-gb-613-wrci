from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


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
    campaign: str | None = Field(default=None, max_length=80)


class RecomputeOut(BaseModel):
    id: int
    valid: bool
    note: str | None = None
