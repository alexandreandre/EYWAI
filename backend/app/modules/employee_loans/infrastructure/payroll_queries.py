"""Requêtes paie liées aux prêts employeur."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List

from app.core.database import supabase
from app.modules.employee_loans.domain.constants import DEFAULT_LEGAL_INTEREST_RATE
from app.modules.employee_loans.domain.rules import compute_interest_benefit_in_kind
from app.modules.employee_loans.infrastructure.queries import (
    TABLE_EMPLOYEE_LOAN_INSTALLMENTS,
    TABLE_EMPLOYEE_LOANS,
)


def get_legal_interest_rate() -> Decimal:
    """Taux d'intérêt légal annuel depuis payroll_config."""
    try:
        res = (
            supabase.table("payroll_config")
            .select("config_data")
            .eq("config_key", "taux_interet_legal")
            .is_("company_id", "null")
            .maybe_single()
            .execute()
        )
        if res and res.data:
            rate = (res.data.get("config_data") or {}).get("taux_annuel")
            if rate is not None:
                return Decimal(str(rate))
    except Exception:
        pass
    return DEFAULT_LEGAL_INTEREST_RATE


def get_active_loans_for_employee(employee_id: str) -> List[Dict[str, Any]]:
    res = (
        supabase.table(TABLE_EMPLOYEE_LOANS)
        .select("*")
        .eq("employee_id", employee_id)
        .eq("status", "active")
        .execute()
    )
    return res.data or []


def get_suspended_loans_with_pending_installment(
    employee_id: str, year: int, month: int
) -> List[Dict[str, Any]]:
    """Prêts suspendus avec échéance pending sur la période (à passer en skipped)."""
    res = (
        supabase.table(TABLE_EMPLOYEE_LOANS)
        .select("*")
        .eq("employee_id", employee_id)
        .eq("status", "suspended")
        .execute()
    )
    loans = res.data or []
    due: List[Dict[str, Any]] = []
    for loan in loans:
        inst = (
            supabase.table(TABLE_EMPLOYEE_LOAN_INSTALLMENTS)
            .select("*")
            .eq("loan_id", loan["id"])
            .eq("year", year)
            .eq("month", month)
            .maybe_single()
            .execute()
        )
        installment = inst.data if inst and inst.data else None
        if installment and installment.get("status") in ("pending", "partial"):
            due.append({**loan, "installment": installment})
    return due


def get_unsettled_installments_for_payroll(
    employee_id: str, payslip_year: int, payslip_month: int
) -> List[Dict[str, Any]]:
    """
    Pour chaque prêt actif : plus ancienne échéance non soldée (pending/partial),
    collectible si sa période <= période bulletin.
    """
    from app.modules.employee_loans.domain.rules import is_installment_collectible

    loans = get_active_loans_for_employee(employee_id)
    due: List[Dict[str, Any]] = []
    for loan in loans:
        inst_res = (
            supabase.table(TABLE_EMPLOYEE_LOAN_INSTALLMENTS)
            .select("*")
            .eq("loan_id", loan["id"])
            .in_("status", ["pending", "partial"])
            .order("installment_number")
            .limit(1)
            .execute()
        )
        rows = inst_res.data or []
        if not rows:
            continue
        installment = rows[0]
        if not is_installment_collectible(
            installment["year"],
            installment["month"],
            payslip_year,
            payslip_month,
        ):
            continue
        due.append({**loan, "installment": installment})
    return due


def get_loans_due_for_period(
    employee_id: str, year: int, month: int
) -> List[Dict[str, Any]]:
    """Deprecated: préférer get_unsettled_installments_for_payroll."""
    return get_unsettled_installments_for_payroll(employee_id, year, month)


def compute_total_loan_benefit_in_kind(
    employee_id: str, year: int, month: int
) -> float:
    """Somme des avantages en nature (intérêts) pour les prêts actifs."""
    legal_rate = get_legal_interest_rate()
    total = Decimal("0")
    for loan in get_active_loans_for_employee(employee_id):
        remaining = Decimal(str(loan.get("remaining_capital", 0)))
        actual_rate = Decimal(str(loan.get("annual_interest_rate", 0)))
        benefit = compute_interest_benefit_in_kind(
            remaining, legal_rate, actual_rate
        )
        total += benefit
    return float(total)


def get_employee_outstanding_loans(employee_id: str) -> Dict[str, Any]:
    res = (
        supabase.table(TABLE_EMPLOYEE_LOANS)
        .select("*, employee:employees(id, first_name, last_name)")
        .eq("employee_id", employee_id)
        .in_("status", ["active", "suspended"])
        .execute()
    )
    loans = res.data or []
    total = sum(float(loan.get("remaining_capital") or 0) for loan in loans)
    return {
        "employee_id": employee_id,
        "total_remaining_capital": round(total, 2),
        "active_loans_count": len(loans),
        "outstanding_loans_count": len(loans),
        "loans": loans,
    }
