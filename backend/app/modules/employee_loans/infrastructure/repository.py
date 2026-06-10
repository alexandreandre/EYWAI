"""Persistance prêts employeur via Supabase."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.employee_loans.domain.interfaces import (
    AbstractEmployeeLoanInstallmentsRepository,
    AbstractEmployeeLoanRepaymentsRepository,
    AbstractEmployeeLoansRepository,
)
from app.modules.employee_loans.infrastructure.queries import (
    SELECT_LOAN_WITH_EMPLOYEE,
    TABLE_EMPLOYEE_LOAN_INSTALLMENTS,
    TABLE_EMPLOYEE_LOAN_REPAYMENTS,
    TABLE_EMPLOYEE_LOANS,
)


def _attach_employee_name(row: Dict[str, Any]) -> Dict[str, Any]:
    employee = row.pop("employee", None) or {}
    if employee:
        first = employee.get("first_name") or ""
        last = employee.get("last_name") or ""
        row["employee_name"] = f"{first} {last}".strip() or None
    return row


class SupabaseEmployeeLoansRepository(AbstractEmployeeLoansRepository):
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data}
        payload.pop("created_at", None)
        if payload.get("id") is None:
            payload.pop("id", None)
        res = supabase.table(TABLE_EMPLOYEE_LOANS).insert(payload).execute()
        if not res.data:
            raise RuntimeError("Insert employee_loans sans données retournées")
        return res.data[0]

    def get_by_id(self, loan_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table(TABLE_EMPLOYEE_LOANS)
            .select(SELECT_LOAN_WITH_EMPLOYEE)
            .eq("id", loan_id)
            .maybe_single()
            .execute()
        )
        if not r or not r.data:
            return None
        return _attach_employee_name(dict(r.data))

    def update(self, loan_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = {**data, "updated_at": datetime.now().isoformat()}
        res = (
            supabase.table(TABLE_EMPLOYEE_LOANS)
            .update(payload)
            .eq("id", loan_id)
            .execute()
        )
        if not res.data:
            return None
        return self.get_by_id(loan_id)

    def delete(self, loan_id: str) -> None:
        supabase.table(TABLE_EMPLOYEE_LOANS).delete().eq("id", loan_id).execute()

    def list_(
        self,
        company_id: str,
        *,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            supabase.table(TABLE_EMPLOYEE_LOANS)
            .select(SELECT_LOAN_WITH_EMPLOYEE)
            .eq("company_id", company_id)
            .order("created_at", desc=True)
        )
        if employee_id:
            query = query.eq("employee_id", employee_id)
        if status:
            query = query.eq("status", status)
        res = query.execute()
        rows = res.data or []
        return [_attach_employee_name(dict(row)) for row in rows]


class SupabaseEmployeeLoanInstallmentsRepository(
    AbstractEmployeeLoanInstallmentsRepository
):
    def bulk_create(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not rows:
            return []
        res = supabase.table(TABLE_EMPLOYEE_LOAN_INSTALLMENTS).insert(rows).execute()
        return res.data or []

    def list_by_loan(self, loan_id: str) -> List[Dict[str, Any]]:
        res = (
            supabase.table(TABLE_EMPLOYEE_LOAN_INSTALLMENTS)
            .select("*")
            .eq("loan_id", loan_id)
            .order("installment_number")
            .execute()
        )
        return res.data or []

    def get_for_period(
        self, loan_id: str, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table(TABLE_EMPLOYEE_LOAN_INSTALLMENTS)
            .select("*")
            .eq("loan_id", loan_id)
            .eq("year", year)
            .eq("month", month)
            .maybe_single()
            .execute()
        )
        return r.data if r and r.data else None

    def update(self, installment_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        res = (
            supabase.table(TABLE_EMPLOYEE_LOAN_INSTALLMENTS)
            .update(data)
            .eq("id", installment_id)
            .execute()
        )
        if not res.data:
            return None
        return res.data[0]

    def skip_pending_for_loan(self, loan_id: str) -> None:
        supabase.table(TABLE_EMPLOYEE_LOAN_INSTALLMENTS).update({"status": "skipped"}).eq(
            "loan_id", loan_id
        ).eq("status", "pending").execute()

    def mark_pending_paid_for_loan(self, loan_id: str) -> None:
        supabase.table(TABLE_EMPLOYEE_LOAN_INSTALLMENTS).update({"status": "paid"}).eq(
            "loan_id", loan_id
        ).eq("status", "pending").execute()


class SupabaseEmployeeLoanRepaymentsRepository(
    AbstractEmployeeLoanRepaymentsRepository
):
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        res = supabase.table(TABLE_EMPLOYEE_LOAN_REPAYMENTS).insert(data).execute()
        if not res.data:
            raise RuntimeError("Insert employee_loan_repayments sans données retournées")
        return res.data[0]

    def list_by_loan(self, loan_id: str) -> List[Dict[str, Any]]:
        res = (
            supabase.table(TABLE_EMPLOYEE_LOAN_REPAYMENTS)
            .select("*")
            .eq("loan_id", loan_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    def get_existing(
        self, loan_id: str, payslip_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table(TABLE_EMPLOYEE_LOAN_REPAYMENTS)
            .select("*")
            .eq("loan_id", loan_id)
            .eq("payslip_id", payslip_id)
            .maybe_single()
            .execute()
        )
        return r.data if r and r.data else None


employee_loans_repository = SupabaseEmployeeLoansRepository()
employee_loan_installments_repository = SupabaseEmployeeLoanInstallmentsRepository()
employee_loan_repayments_repository = SupabaseEmployeeLoanRepaymentsRepository()
