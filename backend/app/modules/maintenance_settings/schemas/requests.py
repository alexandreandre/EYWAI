"""Schémas de requête API maintien de salaire (mise à jour partielle)."""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SubrogationModeLiteral = Literal["when_maintien", "automatic", "at_mp_only", "per_case"]


class MaintenanceSettingsUpdate(BaseModel):
    """Body PUT : tous les champs optionnels."""

    model_config = ConfigDict(extra="forbid")

    apply_legal_maintenance: Optional[bool] = None
    min_seniority_months: Optional[int] = None
    min_seniority_months_at_mp: Optional[int] = None
    employer_waiting_days: Optional[int] = None
    seniority_extension_enabled: Optional[bool] = None
    remove_employer_waiting: Optional[bool] = None
    annual_unique_waiting: Optional[bool] = None
    maintain_100_percent: Optional[bool] = None
    differentiated_at_illness: Optional[bool] = None
    maintain_by_category: Optional[bool] = None
    no_seniority_condition: Optional[bool] = None
    custom_duration_days: Optional[int] = None
    subrogation_mode: Optional[SubrogationModeLiteral] = None
    provident_relay_days: Optional[int] = None
    provident_maintenance_rate: Optional[float] = None
    provident_cadre_only: Optional[bool] = None

    @field_validator("provident_maintenance_rate")
    @classmethod
    def _provident_rate_bounds(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return v
        if v < 0 or v > 1:
            raise ValueError("provident_maintenance_rate doit être entre 0 et 1")
        return v

    @field_validator("employer_waiting_days")
    @classmethod
    def _employer_waiting_bounds(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0 or v > 30:
            raise ValueError("employer_waiting_days doit être entre 0 et 30")
        return v

    @field_validator("min_seniority_months", "min_seniority_months_at_mp")
    @classmethod
    def _seniority_bounds(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        if v < 0 or v > 120:
            raise ValueError("min_seniority_months doit être entre 0 et 120")
        return v
