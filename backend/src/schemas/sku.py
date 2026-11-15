from __future__ import annotations

from pydantic import BaseModel, Field

from src.constants.enums import Category


class SkuIn(BaseModel):
    sku_code: str = Field(min_length=3, max_length=48, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=160)
    category: Category = Category.SOFA
    competitor_id: int = Field(gt=0)
    competitor_item_id: str | None = Field(default=None, max_length=64)
    unit: str = Field(default="件", max_length=16)
    cost: float = Field(ge=0)
    floor_price: float = Field(ge=0)
    target_margin_pct: float = Field(default=15.0, ge=0, le=200)
    current_price: float = Field(gt=0)
    stock: int = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=2000)
    enabled: bool = True


class SkuPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    category: Category | None = None
    competitor_id: int | None = Field(default=None, gt=0)
    competitor_item_id: str | None = Field(default=None, max_length=64)
    unit: str | None = Field(default=None, max_length=16)
    cost: float | None = Field(default=None, ge=0)
    floor_price: float | None = Field(default=None, ge=0)
    target_margin_pct: float | None = Field(default=None, ge=0, le=200)
    current_price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None
