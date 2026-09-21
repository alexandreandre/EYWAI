"""
Schémas de réponse du module saisies_avances.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.shared.pydantic_types import Montant

from .requests import (
    AdvanceType,
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
    amount: Optional[Montant] = None
    calculation_mode: CalculationMode
    percentage: Optional[Montant] = None
    start_date: date
    end_date: Optional[date] = None
    status: SalarySeizureStatus
    priority: int
    document_url: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    # Nom complet joint à la liste (liste RH) ; absent sur le détail.
    employee_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SeizableAmountCalculation(BaseModel):
    """Résultat du calcul de quotité saisissable."""

    net_salary: Montant
    dependents_count: int
    adjusted_salary: Montant
    seizable_amount: Montant
    minimum_untouchable: Montant  # Salaire insaisissable minimum


class SalaryAdvance(BaseModel):
    """Schéma représentant une avance ou un acompte complet depuis la BDD."""

    id: str
    company_id: str
    employee_id: str
    advance_type: AdvanceType = "avance_salaire"
    accounting_account: Optional[str] = None
    requested_amount: Montant
    approved_amount: Optional[Montant] = None
    requested_date: date
    payment_date: Optional[date] = None
    payment_method: Optional[PaymentMethod] = None
    status: SalaryAdvanceStatus
    repayment_mode: RepaymentMode
    repayment_months: int
    remaining_amount: Montant
    remaining_to_pay: Optional[float] = (
        None  # Montant restant à verser (calculé dynamiquement)
    )
    request_comment: Optional[str] = None
    rejection_reason: Optional[str] = None
    prime_label: Optional[str] = None
    prime_id: Optional[str] = None
    prime_expected_amount: Optional[Montant] = None
    prime_final_amount: Optional[Montant] = None
    prime_reconciled_at: Optional[datetime] = None
    prime_reconciled_payslip_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    plafond_net_override: bool = False
    plafond_net_override_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdvanceAvailableAmount(BaseModel):
    """Montant disponible pour une avance ou un acompte."""

    advance_type: AdvanceType = "avance_salaire"
    daily_salary: Montant
    days_worked: Montant
    outstanding_advances: Montant
    available_amount: Montant
    max_advance_days: int = 10
    reference_net_salary: Montant = Decimal("0")
    reference_payslip_year: Optional[int] = None
    reference_payslip_month: Optional[int] = None
    max_advance_from_net: Montant = Decimal("0")
    max_advance_net_ratio: Montant = Decimal("0.5")
    is_employee_right: bool = False


class SalarySeizureDeduction(BaseModel):
    """Historique d'un prélèvement de saisie."""

    id: str
    seizure_id: str
    payslip_id: str
    year: int
    month: int
    gross_salary: Montant
    net_salary: Montant
    seizable_amount: Montant
    deducted_amount: Montant
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SalaryAdvanceRepayment(BaseModel):
    """Historique d'un remboursement d'avance."""

    id: str
    advance_id: str
    payslip_id: str
    year: int
    month: int
    repayment_amount: Montant
    remaining_after: Montant
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
    montant: Montant
    creditor_name: str
    reference: Optional[str] = None


class PayslipAdvanceRepaymentInfo(BaseModel):
    """Information de remboursement d'avance pour un bulletin."""

    montant: Montant
    date_avance: date
    reste_apres: Montant


class PayslipDeductionsEnrichment(BaseModel):
    """Enrichissement du bulletin avec saisies et avances."""

    retenues_saisies: dict
    remboursements_avances: dict


class SalaryAdvancePayment(BaseModel):
    """Schéma représentant un paiement d'avance."""

    id: str
    advance_id: str
    company_id: str
    payment_amount: Montant
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
