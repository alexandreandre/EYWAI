"""
Répositories Supabase pour saisies et avances.

Implémentation des interfaces domain (ISeizureRepository, IAdvanceRepository,
IAdvancePaymentRepository, IEmployeeCompanyProvider).
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.saisies_avances.domain.interfaces import (
    IAdvancePaymentRepository,
    IAdvanceRepository,
    IEmployeeCompanyProvider,
    ISeizureRepository,
)


class SeizureRepository(ISeizureRepository):
    """Accès table salary_seizures."""

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("salary_seizures").insert(data).execute()
        if not r.data:
            raise ValueError("Insert failed")
        return r.data[0]

    def get_by_id(self, seizure_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("salary_seizures")
            .select("*")
            .eq("id", seizure_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def list_(
        self,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("salary_seizures").select("*")
        if employee_id:
            q = q.eq("employee_id", employee_id)
        if status:
            q = q.eq("status", status)
        r = q.order("created_at", desc=True).execute()
        return r.data or []

    def update(self, seizure_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("salary_seizures")
            .update(data)
            .eq("id", seizure_id)
            .execute()
        )
        return r.data[0] if r.data else None

    def delete(self, seizure_id: str) -> None:
        supabase.table("salary_seizures").delete().eq("id", seizure_id).execute()


class AdvanceRepository(IAdvanceRepository):
    """Accès table salary_advances."""

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("salary_advances").insert(data).execute()
        if not r.data:
            raise ValueError("Insert failed")
        return r.data[0]

    def get_by_id(self, advance_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("salary_advances")
            .select("*")
            .eq("id", advance_id)
            .single()
            .execute()
        )
        return r.data if r.data else None

    def list_(
        self,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = supabase.table("salary_advances").select("*")
        if employee_id:
            q = q.eq("employee_id", employee_id)
        if status:
            q = q.eq("status", status)
        r = q.order("created_at", desc=True).execute()
        return r.data or []

    def update(self, advance_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("salary_advances")
            .update(data)
            .eq("id", advance_id)
            .execute()
        )
        return r.data[0] if r.data else None


class AdvancePaymentRepository(IAdvancePaymentRepository):
    """Accès table salary_advance_payments."""

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("salary_advance_payments").insert(data).execute()
        if not r.data:
            raise ValueError("Insert failed")
        return r.data[0]

    def list_by_advance_id(self, advance_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("salary_advance_payments")
            .select("*")
            .eq("advance_id", advance_id)
            .order("payment_date", desc=True)
            .execute()
        )
        return r.data or []

    def get_total_paid_by_advance_id(self, advance_id: str) -> Decimal:
        r = (
            supabase.table("salary_advance_payments")
            .select("payment_amount")
            .eq("advance_id", advance_id)
            .execute()
        )
        return sum(Decimal(str(p.get("payment_amount", 0))) for p in (r.data or []))

    def delete(self, payment_id: str) -> None:
        supabase.table("salary_advance_payments").delete().eq(
            "id", payment_id
        ).execute()


class EmployeeCompanyProvider(IEmployeeCompanyProvider):
    """Lecture company_id depuis table employees."""

    def get_company_id(self, employee_id: str) -> Optional[str]:
        r = (
            supabase.table("employees")
            .select("company_id")
            .eq("id", employee_id)
            .single()
            .execute()
        )
        return r.data.get("company_id") if r.data else None


# Singletons utilisés par le service (injectables si besoin)
seizure_repository = SeizureRepository()
advance_repository = AdvanceRepository()
advance_payment_repository = AdvancePaymentRepository()
employee_company_provider = EmployeeCompanyProvider()
