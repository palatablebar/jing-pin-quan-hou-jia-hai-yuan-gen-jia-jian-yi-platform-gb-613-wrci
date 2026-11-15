from __future__ import annotations

from pydantic import BaseModel, Field

from src.constants.enums import RuleStrategy


class RuleIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=120)
    scope_kind: str = Field(default="global", pattern=r"^(global|competitor|category|sku)$")
    scope_value: str | None = Field(default=None, max_length=64)
    sku_id: int | None = Field(default=None, gt=0)
    competitor_id: int | None = Field(default=None, gt=0)
    strategy: RuleStrategy = RuleStrategy.GUARDED
    target_margin_pct: float = Field(default=15.0, ge=0, le=200)
    max_drop_pct: float = Field(default=15.0, ge=0, le=100)
    priority: int = Field(default=100, ge=0, le=1000)
    enabled: bool = True
    note: str | None = Field(default=None, max_length=2000)


class RulePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    scope_kind: str | None = Field(default=None, pattern=r"^(global|competitor|category|sku)$")
    scope_value: str | None = Field(default=None, max_length=64)
    sku_id: int | None = Field(default=None, gt=0)
    competitor_id: int | None = Field(default=None, gt=0)
    strategy: RuleStrategy | None = None
    target_margin_pct: float | None = Field(default=None, ge=0, le=200)
    max_drop_pct: float | None = Field(default=None, ge=0, le=100)
    priority: int | None = Field(default=None, ge=0, le=1000)
    enabled: bool | None = None
    note: str | None = Field(default=None, max_length=2000)
