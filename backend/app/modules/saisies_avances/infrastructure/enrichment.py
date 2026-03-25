"""
Écritures et lectures liées à l'enrichissement bulletin (saisies / avances).

Historique : salary_seizure_deductions, salary_advance_repayments.
Utilisé par application.service.enrich_payslip. Comportement identique au legacy
services.saisies_avances_integration pour les écritures et vérifications d'existence.
"""

from typing import Any, Dict, Optional

from app.core.database import supabase


def get_existing_deduction(
    seizure_id: str, payslip_id: str
) -> Optional[Dict[str, Any]]:
    """Vérifie si une déduction pour cette saisie et ce bulletin existe déjà."""
    r = (
        supabase.table("salary_seizure_deductions")
        .select("id")
        .eq("seizure_id", seizure_id)
        .eq("payslip_id", payslip_id)
        .maybe_single()
        .execute()
    )
    return r.data if r.data else None


def get_existing_repayment(
    advance_id: str, payslip_id: str
) -> Optional[Dict[str, Any]]:
    """Récupère le remboursement déjà enregistré pour cette avance et ce bulletin."""
    r = (
        supabase.table("salary_advance_repayments")
        .select("id, repayment_amount, remaining_after")
        .eq("advance_id", advance_id)
        .eq("payslip_id", payslip_id)
        .maybe_single()
        .execute()
    )
    return r.data if r.data else None


def insert_seizure_deduction(
    seizure_id: str,
    payslip_id: str,
    year: int,
    month: int,
    gross_salary: float,
    net_salary: float,
    seizable_amount: float,
    deducted_amount: float,
) -> None:
    """Enregistre une ligne d'historique de prélèvement saisie sur bulletin."""
    supabase.table("salary_seizure_deductions").insert(
        {
            "seizure_id": seizure_id,
            "payslip_id": payslip_id,
            "year": year,
            "month": month,
            "gross_salary": gross_salary,
            "net_salary": net_salary,
            "seizable_amount": seizable_amount,
            "deducted_amount": deducted_amount,
        }
    ).execute()


def insert_advance_repayment(
    advance_id: str,
    payslip_id: str,
    year: int,
    month: int,
    repayment_amount: float,
    remaining_after: float,
) -> None:
    """Enregistre une ligne d'historique de remboursement d'avance sur bulletin."""
    supabase.table("salary_advance_repayments").insert(
        {
            "advance_id": advance_id,
            "payslip_id": payslip_id,
            "year": year,
            "month": month,
            "repayment_amount": repayment_amount,
            "remaining_after": remaining_after,
        }
    ).execute()
