"""
Schémas de réponse du module saisies_avances.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from .requests import (
    CalculationMode,
    PaymentMethod,
    RepaymentMode,
    SalaryAdvanceStatus,
    SalarySeizureStatus,
    SalarySeizureType,
)


class SalarySeizure(BaseModel):
    """Schéma représentant une saisie complète depuis la BDD."""
    id: str
    company_id: str
    employee_id: str
    type: SalarySeizureType
    reference_legale: Optional[str] = None
    creditor_name: str
    creditor_iban: Optional[str] = None
    amount: Optional[Decimal] = None
    calculation_mode: CalculationMode
    percentage: Optional[Decimal] = None
    start_date: date
    end_date: Optional[date] = None
    status: SalarySeizureStatus
    priority: int
    document_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SeizableAmountCalculation(BaseModel):
    """Résultat du calcul de quotité saisissable."""
    net_salary: Decimal
    dependents_count: int
    adjusted_salary: Decimal
    seizable_amount: Decimal
    minimum_untouchable: Decimal  # Salaire insaisissable minimum


class SalaryAdvance(BaseModel):
    """Schéma représentant une avance complète depuis la BDD."""
    id: str
    company_id: str
    employee_id: str
    requested_amount: Decimal
    approved_amount: Optional[Decimal] = None
    requested_date: date
    payment_date: Optional[date] = None
    payment_method: Optional[PaymentMethod] = None
    status: SalaryAdvanceStatus
    repayment_mode: RepaymentMode
    repayment_months: int
    remaining_amount: Decimal
    remaining_to_pay: Optional[float] = None  # Montant restant à verser (calculé dynamiquement)
    request_comment: Optional[str] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AdvanceAvailableAmount(BaseModel):
    """Montant disponible pour une avance."""
    daily_salary: Decimal
    days_worked: Decimal
    outstanding_advances: Decimal
    available_amount: Decimal
    max_advance_days: int = 10


class SalarySeizureDeduction(BaseModel):
    """Historique d'un prélèvement de saisie."""
    id: str
    seizure_id: str
    payslip_id: str
    year: int
    month: int
    gross_salary: Decimal
    net_salary: Decimal
    seizable_amount: Decimal
    deducted_amount: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SalaryAdvanceRepayment(BaseModel):
    """Historique d'un remboursement d'avance."""
    id: str
    advance_id: str
    payslip_id: str
    year: int
    month: int
    repayment_amount: Decimal
    remaining_after: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SalarySeizureWithEmployee(BaseModel):
    """Saisie avec informations de l'employé."""
    seizure: SalarySeizure
    employee_first_name: str
    employee_last_name: str


class SalaryAdvanceWithEmployee(BaseModel):
    """Avance avec informations de l'employé."""
    advance: SalaryAdvance
    employee_first_name: str
    employee_last_name: str


class PayslipSeizureInfo(BaseModel):
    """Information de saisie pour un bulletin."""
    type: str
    montant: Decimal
    creditor_name: str
    reference: Optional[str] = None


class PayslipAdvanceRepaymentInfo(BaseModel):
    """Information de remboursement d'avance pour un bulletin."""
    montant: Decimal
    date_avance: date
    reste_apres: Decimal


class PayslipDeductionsEnrichment(BaseModel):
    """Enrichissement du bulletin avec saisies et avances."""
    retenues_saisies: dict
    remboursements_avances: dict


class SalaryAdvancePayment(BaseModel):
    """Schéma représentant un paiement d'avance."""
    id: str
    advance_id: str
    company_id: str
    payment_amount: Decimal
    payment_date: date
    payment_method: Optional[PaymentMethod] = None
    proof_file_path: Optional[str] = None
    proof_file_name: Optional[str] = None
    proof_file_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    created_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SignedUploadURL(BaseModel):
    """URL signée pour upload de preuve de paiement."""
    path: str
    signedURL: str


__all__ = [
    "SalarySeizure",
    "SalaryAdvance",
    "SeizableAmountCalculation",
    "AdvanceAvailableAmount",
    "SalarySeizureDeduction",
    "SalaryAdvanceRepayment",
    "SalarySeizureWithEmployee",
    "SalaryAdvanceWithEmployee",
    "PayslipSeizureInfo",
    "PayslipAdvanceRepaymentInfo",
    "PayslipDeductionsEnrichment",
    "SalaryAdvancePayment",
    "SignedUploadURL",
]
