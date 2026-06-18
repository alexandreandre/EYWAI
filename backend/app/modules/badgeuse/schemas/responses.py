from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DayAccountingFields(BaseModel):
    computed_seconds: int
    accounted_seconds: Optional[int] = None
    effective_seconds: int
    has_override: bool
    override_differs_from_computed: bool
