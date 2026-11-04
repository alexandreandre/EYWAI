"""Schémas de requête prêts employeur."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Un compte par prêt (OD de paie) : 3 à 20 chiffres, espaces retirés
#: (42511000 ; 42590009). Vide : le prêt suit le compte de la société.
COMPTE_DU_PRET_MAX = 20


def _compte_du_pret(valeur: Optional[str]) -> Optional[str]:
    if valeur is None:
        return None
    compte = "".join(str(valeur).split())
    if not compte:
        return None
    if not (compte.isascii() and compte.isdigit()) or not 3 <= len(compte) <= COMPTE_DU_PRET_MAX:
        raise ValueError(
            "Numéro de compte du prêt illisible : des chiffres seulement, "
            f"de 3 à {COMPTE_DU_PRET_MAX} (ex. 42511000), ou vide pour le compte de la société."
        )
    return compte


class EmployeeLoanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str
    principal_amount: float = Field(gt=0)
    annual_interest_rate: float = Field(default=0, ge=0, le=1)
    start_date: date
    duration_months: int = Field(ge=1, le=360)
    repayment_day: int = Field(default=1, ge=1, le=28)
    reason: Optional[str] = None
    notes: Optional[str] = None
    # Compte où le prêt a été versé ; son remboursement le solde dans l'OD.
    accounting_account: Optional[str] = None
    activate: bool = True

    _compte = field_validator("accounting_account", mode="before")(_compte_du_pret)


class EmployeeLoanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[
        Literal["draft", "active", "suspended", "repaid", "cancelled", "defaulted"]
    ] = None
    declared_2062: Optional[bool] = None
    notes: Optional[str] = None
    accounting_account: Optional[str] = None

    _compte = field_validator("accounting_account", mode="before")(_compte_du_pret)


class AmortizationPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_amount: float = Field(gt=0)
    annual_interest_rate: float = Field(default=0, ge=0, le=1)
    start_date: date
    duration_months: int = Field(ge=1, le=360)


class EarlyRepaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(gt=0)
    repayment_date: date
