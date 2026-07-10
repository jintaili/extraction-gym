"""SROIE receipt extraction schema: the four official ICDAR-2019 Task 3 fields."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ReceiptExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str | None
    date: str | None
    address: str | None
    total: str | None
