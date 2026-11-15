from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class RunIn(BaseModel):
    captured_on: date | None = None
    competitor_id: int | None = Field(default=None, gt=0)
    trigger: str = Field(default="manual", pattern=r"^(manual|schedule)$")
    params: dict = Field(default_factory=dict)
