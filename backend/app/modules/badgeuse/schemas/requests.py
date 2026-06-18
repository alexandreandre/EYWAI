from __future__ import annotations

from pydantic import BaseModel, Field


class SetAccountedHoursRequest(BaseModel):
    accounted_seconds: int = Field(
        ...,
        ge=0,
        le=86400,
        description="Durée comptabilisée en secondes (0 à 24h)",
    )
