"""
Schémas de requête du module saisies_avances.
"""

from datetime import date
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

# Types / Literals (partagés avec responses)
SalarySeizureType = Literal["saisie_arret", "pension_alimentaire", "atd", "satd"]
SalarySeizureStatus = Literal["active", "suspended", "closed"]
CalculationMode = Literal["fixe", "pourcentage", "barème_legal"]
SalaryAdvanceStatus = Literal["pending", "approved", "rejected", "paid"]
RepaymentMode = Literal["single", "multiple"]
PaymentMethod = Literal["virement", "cheque", "especes"]


class SalarySeizureCreate(BaseModel):
    """Schéma pour la création d'une saisie sur salaire."""

    employee_id: str
    type: SalarySeizureType
    reference_legale: Optional[str] = None
    creditor_name: str
    creditor_iban: Optional[str] = None
    amount: Optional[Decimal] = None
    calculation_mode: CalculationMode = "barème_legal"
    percentage: Optional[Decimal] = None  # Si calculation_mode = 'pourcentage'
    start_date: date
    end_date: Optional[date] = None
    priority: int = Field(default=4, ge=1, le=4)
    document_url: Optional[str] = None
    notes: Optional[str] = None


class SalarySeizureUpdate(BaseModel):
    """Schéma pour la mise à jour d'une saisie."""

    status: Optional[SalarySeizureStatus] = None
    amount: Optional[Decimal] = None
    calculation_mode: Optional[CalculationMode] = None
    percentage: Optional[Decimal] = None
    end_date: Optional[date] = None
    notes: Optional[str] = None


class SalaryAdvanceCreate(BaseModel):
    """Schéma pour la création d'une demande d'avance."""

    employee_id: str
    requested_amount: Decimal = Field(gt=0)
    requested_date: date
    repayment_mode: RepaymentMode = "single"
    repayment_months: int = Field(default=1, ge=1, le=12)
    request_comment: Optional[str] = None


class SalaryAdvanceApprove(BaseModel):
    """Schéma pour l'approbation d'une avance."""

    approved_amount: Optional[Decimal] = None  # Si None, utilise requested_amount
    payment_method: PaymentMethod = "virement"
    repayment_mode: Optional[RepaymentMode] = None
    repayment_months: Optional[int] = None


class SalaryAdvanceReject(BaseModel):
    """Schéma pour le rejet d'une avance."""

    rejection_reason: str


class SalaryAdvancePaymentCreate(BaseModel):
    """Schéma pour créer un paiement d'avance."""

    advance_id: str
    payment_amount: Decimal
    payment_date: date
    payment_method: Optional[PaymentMethod] = None
    proof_file_path: Optional[str] = None
    proof_file_name: Optional[str] = None
    proof_file_type: Optional[str] = None
    notes: Optional[str] = None


class SalaryAdvancePaymentUpdate(BaseModel):
    """Schéma pour mettre à jour un paiement d'avance."""

    payment_amount: Optional[Decimal] = None
    payment_date: Optional[date] = None
    payment_method: Optional[PaymentMethod] = None
    proof_file_path: Optional[str] = None
    proof_file_name: Optional[str] = None
    proof_file_type: Optional[str] = None
    notes: Optional[str] = None


__all__ = [
    "SalarySeizureType",
    "SalarySeizureStatus",
    "CalculationMode",
    "SalaryAdvanceStatus",
    "RepaymentMode",
    "PaymentMethod",
    "SalarySeizureCreate",
    "SalarySeizureUpdate",
    "SalaryAdvanceCreate",
    "SalaryAdvanceApprove",
    "SalaryAdvanceReject",
    "SalaryAdvancePaymentCreate",
    "SalaryAdvancePaymentUpdate",
]
