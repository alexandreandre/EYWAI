"""
Repository expenses (implémentation Supabase).

Logique extraite de api/routers/expenses.py — comportement identique.
Utilise les constantes de infrastructure.queries (table, select, order).
"""
from typing import Any, Dict, List, Optional

from app.modules.expenses.domain.interfaces import IExpenseRepository
from app.modules.expenses.infrastructure.queries import (
    ORDER_BY_CREATED_AT_DESC,
    ORDER_BY_DATE_DESC,
    SELECT_ALL_WITH_EMPLOYEE,
    TABLE_EXPENSE_REPORTS,
)


class ExpenseRepository(IExpenseRepository):
    """Implémentation Supabase pour expense_reports."""

    def __init__(self, supabase_client: Any = None):
        if supabase_client is None:
            from app.core.database import supabase
            supabase_client = supabase
        self._client = supabase_client

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self._client.table(TABLE_EXPENSE_REPORTS).insert(data).execute()
        if not response.data:
            raise ValueError("Échec de la création de la note de frais.")
        return response.data[0]

    def get_by_id(self, expense_id: str) -> Optional[Dict[str, Any]]:
        response = self._client.table(TABLE_EXPENSE_REPORTS).select("*").eq("id", expense_id).execute()
        if not response.data or len(response.data) == 0:
            return None
        return response.data[0]

    def update_status(self, expense_id: str, status: str) -> Optional[Dict[str, Any]]:
        response = (
            self._client.table(TABLE_EXPENSE_REPORTS)
            .update({"status": status})
            .eq("id", expense_id)
            .execute()
        )
        if not response.data:
            return None
        return response.data[0]

    def list_by_employee_id(self, employee_id: str) -> List[Dict[str, Any]]:
        response = (
            self._client.table(TABLE_EXPENSE_REPORTS)
            .select("*")
            .eq("employee_id", employee_id)
            .order(ORDER_BY_DATE_DESC, desc=True)
            .execute()
        )
        return response.data or []

    def list_all(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query = self._client.table(TABLE_EXPENSE_REPORTS).select(
            SELECT_ALL_WITH_EMPLOYEE
        )
        if status:
            query = query.eq("status", status)
        response = query.order(ORDER_BY_CREATED_AT_DESC, desc=True).execute()
        return response.data or []
