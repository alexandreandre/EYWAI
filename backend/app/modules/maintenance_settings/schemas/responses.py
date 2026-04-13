"""Schémas de réponse API maintien de salaire."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SubrogationMode = Literal["automatic", "at_mp_only", "per_case"]


class MaintenanceSettings(BaseModel):
    """Configuration maintien de salaire (ligne BDD ou valeurs par défaut)."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    company_id: str
    apply_legal_maintenance: bool = True
    min_seniority_months: int = Field(default=12, ge=0, le=120)
    employer_waiting_days: int = Field(default=7, ge=0, le=30)
    seniority_extension_enabled: bool = False
    remove_employer_waiting: bool = False
    annual_unique_waiting: bool = False
    maintain_100_percent: bool = False
    differentiated_at_illness: bool = False
    maintain_by_category: bool = False
    no_seniority_condition: bool = False
    custom_duration_days: Optional[int] = None
    subrogation_mode: SubrogationMode = "automatic"
    provident_relay_days: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
