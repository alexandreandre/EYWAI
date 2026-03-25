"""
Repository employés et profils : persistance Supabase (tables employees, profiles).

Implémente les ports du domain. Comportement identique au router legacy.
"""

from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.employees.domain.interfaces import (
    IEmployeeRepository,
    IProfileRepository,
)


class EmployeeRepository(IEmployeeRepository):
    """Implémentation Supabase de IEmployeeRepository."""

    def get_by_company(self, company_id: str) -> List[Dict[str, Any]]:
        response = (
            supabase.table("employees")
            .select("*")
            .eq("company_id", company_id)
            .order("last_name")
            .execute()
        )
        return [dict(row) for row in (response.data or [])]

    def get_by_id(self, employee_id: str, company_id: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employees")
            .select("*")
            .eq("id", employee_id)
            .eq("company_id", company_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return dict(response.data)

    def get_by_id_only(self, employee_id: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employees")
            .select("*")
            .eq("id", employee_id)
            .single()
            .execute()
        )
        if not response.data:
            return None
        return dict(response.data)

    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = supabase.table("employees").insert(data).execute()
        if not response.data:
            raise RuntimeError("Insert employees returned no data")
        return dict(response.data[0])

    def update(
        self, employee_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employees").update(data).eq("id", employee_id).execute()
        )
        if not response.data:
            return None
        return dict(response.data[0])

    def delete(self, employee_id: str) -> bool:
        supabase.table("employees").delete().eq("id", employee_id).execute()
        return True


class ProfileRepository(IProfileRepository):
    """Implémentation Supabase de IProfileRepository (table profiles)."""

    def upsert(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        response = supabase.table("profiles").upsert(profile_data).execute()
        if not response.data:
            raise RuntimeError("Upsert profiles returned no data")
        data = response.data
        first = data[0] if isinstance(data, list) else data
        return dict(first) if first is not None else {}
