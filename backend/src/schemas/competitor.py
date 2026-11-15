from __future__ import annotations

from pydantic import BaseModel, Field

from src.constants.enums import Platform


class CompetitorIn(BaseModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=2, max_length=120)
    platform: Platform = Platform.TAOBAO
    shop_url: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=2000)
    capture_config: dict = Field(default_factory=dict)
    enabled: bool = True


class CompetitorPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    platform: Platform | None = None
    shop_url: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=40)
    note: str | None = Field(default=None, max_length=2000)
    capture_config: dict | None = None
    enabled: bool | None = None
