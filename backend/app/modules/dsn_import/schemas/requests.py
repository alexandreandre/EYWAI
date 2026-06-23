"""Schémas entrée API import DSN."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class WorkforceResolution(BaseModel):
    gap_id: str
    employee_id: str
    action: Literal[
        "open_exit",
        "close_departure",
        "ignore",
        "acknowledge_new_hire",
        "delete_permanently",
    ]
    exit_type: Optional[str] = None
    last_working_day: Optional[date] = None
    exit_reason: Optional[str] = None
    ignore_reason: Optional[str] = None


class DsnImportCommitBody(BaseModel):
    overrides: Dict[str, str] = Field(default_factory=dict)
    payload_edits: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    target_company_id: Optional[str] = Field(
        default=None,
        description="Rattacher l'import à une entreprise existante (sinon auto par SIRET)",
    )
    import_mode: Optional[str] = Field(
        default=None,
        description="onboarding | monthly — contexte d'import pour le suivi couverture",
    )
    replace_existing_periods: bool = Field(
        default=False,
        description=(
            "Consentement UX : l'utilisateur confirme le remplacement des cumuls "
            "d'une période déjà importée. L'écrasement sur disque est effectif "
            "via write_cumuls_file au commit, indépendamment de ce flag."
        ),
    )
    workforce_resolutions: List[WorkforceResolution] = Field(default_factory=list)
    remove_orphan_imported_employees: bool = Field(
        default=False,
        description=(
            "Réimport mensuel : supprimer les salariés créés par import DSN "
            "(email *.dsn-import.local, sans compte activé) absents du fichier analysé."
        ),
    )


class DsnImportParseQuery(BaseModel):
    import_mode: Optional[str] = Field(default="onboarding")
    target_company_id: Optional[str] = None


class DsnImportRevalidateBody(BaseModel):
    payload_edits: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    target_company_id: Optional[str] = None


class DsnImportWorkforceResolutionsBody(BaseModel):
    resolutions: List[WorkforceResolution] = Field(default_factory=list)


class ActivateImportedEmployeeBody(BaseModel):
    employee_id: str
    company_id: str
    email: EmailStr


class DsnImportRevokePeriodBody(BaseModel):
    company_id: str = Field(description="Entreprise concernée")
    period: str = Field(description="Période YYYY-MM à révoquer")
