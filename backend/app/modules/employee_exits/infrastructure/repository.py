"""
Repositories du module employee_exits — implémentations des ports domain.

Accès Supabase (tables employee_exits, exit_documents, exit_checklist_items).
Comportement identique à api/routers/employee_exits.py.
"""

from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.employee_exits.domain.interfaces import (
    IEmployeeExitRepository,
    IExitChecklistRepository,
    IExitDocumentRepository,
)

EMPLOYEE_FKEY = "employees!employee_exits_employee_id_fkey"


class EmployeeExitRepository(IEmployeeExitRepository):
    """Implémentation Supabase pour employee_exits."""

    def __init__(self, client: Any = None):
        self._sb = client or supabase

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self._sb.table("employee_exits").insert(data).execute()
        if not response.data:
            raise RuntimeError("Échec de la création du processus de sortie")
        return response.data[0]

    def get_by_id(self, exit_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            self._sb.table("employee_exits")
            .select("*")
            .eq("id", exit_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def get_with_employee(
        self, exit_id: str, company_id: str, employee_columns: str
    ) -> Optional[Dict[str, Any]]:
        sel = f"*, {EMPLOYEE_FKEY}({employee_columns})"
        r = (
            self._sb.table("employee_exits")
            .select(sel)
            .eq("id", exit_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def list(
        self,
        company_id: str,
        status: Optional[str] = None,
        exit_type: Optional[str] = None,
        employee_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            self._sb.table("employee_exits")
            .select(f"*, {EMPLOYEE_FKEY}(id, first_name, last_name, email, job_title)")
            .eq("company_id", company_id)
        )
        if status:
            query = query.eq("status", status)
        if exit_type:
            query = query.eq("exit_type", exit_type)
        if employee_id:
            query = query.eq("employee_id", employee_id)
        result = query.order("created_at", desc=True).execute()
        return result.data or []

    def update(
        self, exit_id: str, company_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        resp = (
            self._sb.table("employee_exits")
            .update(data)
            .eq("id", exit_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not resp.data:
            return None
        return resp.data[0] if isinstance(resp.data, list) else resp.data

    def delete(self, exit_id: str, company_id: str) -> bool:
        self._sb.table("employee_exits").delete().eq("id", exit_id).eq(
            "company_id", company_id
        ).execute()
        return True


class ExitDocumentRepository(IExitDocumentRepository):
    """Implémentation Supabase pour exit_documents."""

    def __init__(self, client: Any = None):
        self._sb = client or supabase

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self._sb.table("exit_documents").insert(data).execute()
        if not response.data:
            raise RuntimeError("Échec de la création du document")
        return response.data[0]

    def list_by_exit(self, exit_id: str, company_id: str) -> List[Dict[str, Any]]:
        r = (
            self._sb.table("exit_documents")
            .select("*")
            .eq("exit_id", exit_id)
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .execute()
        )
        return r.data or []

    def get_by_id(
        self, document_id: str, exit_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            self._sb.table("exit_documents")
            .select("*")
            .eq("id", document_id)
            .eq("exit_id", exit_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def update(
        self, document_id: str, exit_id: str, company_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        resp = (
            self._sb.table("exit_documents")
            .update(data)
            .eq("id", document_id)
            .eq("exit_id", exit_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not resp.data:
            return None
        return resp.data[0] if isinstance(resp.data, list) else resp.data

    def delete(self, document_id: str, exit_id: str, company_id: str) -> bool:
        self._sb.table("exit_documents").delete().eq("id", document_id).eq(
            "exit_id", exit_id
        ).eq("company_id", company_id).execute()
        return True


class ExitChecklistRepository(IExitChecklistRepository):
    """Implémentation Supabase pour exit_checklist_items."""

    def __init__(self, client: Any = None):
        self._sb = client or supabase

    def create_many(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        response = self._sb.table("exit_checklist_items").insert(items).execute()
        return response.data or []

    def list_by_exit(self, exit_id: str, company_id: str) -> List[Dict[str, Any]]:
        r = (
            self._sb.table("exit_checklist_items")
            .select("*")
            .eq("exit_id", exit_id)
            .eq("company_id", company_id)
            .order("display_order")
            .execute()
        )
        return r.data or []

    def get_item(
        self, item_id: str, exit_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            self._sb.table("exit_checklist_items")
            .select("*")
            .eq("id", item_id)
            .eq("exit_id", exit_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return r.data if r.data else None

    def add_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self._sb.table("exit_checklist_items").insert(data).execute()
        if not response.data:
            raise RuntimeError("Échec de la création de l'item")
        return response.data[0]

    def update_item(
        self, item_id: str, exit_id: str, company_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        resp = (
            self._sb.table("exit_checklist_items")
            .update(data)
            .eq("id", item_id)
            .eq("exit_id", exit_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not resp.data:
            return None
        return resp.data[0] if isinstance(resp.data, list) else resp.data

    def delete_item(self, item_id: str, exit_id: str, company_id: str) -> bool:
        self._sb.table("exit_checklist_items").delete().eq("id", item_id).eq(
            "exit_id", exit_id
        ).eq("company_id", company_id).execute()
        return True
