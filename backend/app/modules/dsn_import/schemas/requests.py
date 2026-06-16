"""Schémas entrée API import DSN."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field


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
        description="Remplacer les cumuls des périodes déjà importées",
    )


class DsnImportParseQuery(BaseModel):
    import_mode: Optional[str] = Field(default="onboarding")
    target_company_id: Optional[str] = None


class DsnImportRevalidateBody(BaseModel):
    payload_edits: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    target_company_id: Optional[str] = None


class ActivateImportedEmployeeBody(BaseModel):
    employee_id: str
    company_id: str
    email: EmailStr
