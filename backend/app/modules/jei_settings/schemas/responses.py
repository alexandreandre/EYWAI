"""Schémas de réponse API paramétrage JEI."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class JeiSettings(BaseModel):
    """Configuration JEI (ligne BDD ou valeurs par défaut)."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    company_id: str
    jei_enabled: bool = False
    date_creation_etablissement: Optional[date] = None
    taux_exoneration: float = Field(default=1.0, ge=0, le=1)
    annees_restantes: Optional[int] = None
    date_fin_eligibilite: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
