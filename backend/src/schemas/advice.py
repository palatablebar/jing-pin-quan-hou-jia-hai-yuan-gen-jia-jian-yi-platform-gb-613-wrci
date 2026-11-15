from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DecisionIn(BaseModel):
    status: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=1000)
    approved_price: float | None = Field(default=None, gt=0, le=1_000_000)
