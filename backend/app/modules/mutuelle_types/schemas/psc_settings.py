"""Schémas PSC entreprise."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PscSettingsResponse(BaseModel):
    company_id: str
    mutuelle_organisme_label: str | None = None
    mutuelle_employee_self_service: bool = False


class PscSettingsUpdate(BaseModel):
    mutuelle_organisme_label: str | None = Field(None, max_length=128)
    mutuelle_employee_self_service: bool | None = None


class EmployeeMutuelleChoiceRequest(BaseModel):
    mutuelle_type_id: str = Field(..., min_length=1)


class EmployeeMutuelleOption(BaseModel):
    id: str
    libelle: str
    montant_salarial: float
    montant_patronal: float
    pack_couverture: str | None = None
    statut_categoriel: str | None = None
    organisme_label: str | None = None
    organisme_display: str | None = None
    note: str | None = None
    code_option_dsn: str | None = None


class EmployeeMutuelleChoicesResponse(BaseModel):
    organisme_label: str | None = None
    self_service_enabled: bool = False
    current_mutuelle_type_id: str | None = None
    options: list[EmployeeMutuelleOption]
