"""Schémas de requête API paramétrage JEI."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class JeiSettingsUpdate(BaseModel):
    """Body PUT : tous les champs optionnels."""

    model_config = ConfigDict(extra="forbid")

    jei_enabled: Optional[bool] = None
    date_creation_etablissement: Optional[date] = None
    taux_exoneration: Optional[float] = Field(default=None, ge=0, le=1)

    @field_validator("date_creation_etablissement", mode="before")
    @classmethod
    def _empty_date_to_none(cls, v: object) -> object:
        if v == "" or v is None:
            return None
        return v
