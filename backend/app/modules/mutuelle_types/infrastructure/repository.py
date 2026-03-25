"""
Implémentation du port IMutuelleTypeRepository via Supabase.

Tables : company_mutuelle_types, employee_mutuelle_types, employees.specificites_paie.
Pas de FastAPI ; uniquement accès DB et mappers.
"""

from __future__ import annotations

from typing import Any

from app.modules.mutuelle_types.domain.entities import MutuelleType
from app.modules.mutuelle_types.infrastructure.mappers import (
    mutuelle_type_to_row,
    row_to_mutuelle_type,
)


class SupabaseMutuelleTypeRepository:
    """Repository mutuelle_types sur company_mutuelle_types + employee_mutuelle_types."""

    def __init__(self, supabase_client: Any) -> None:
        self._supabase = supabase_client

    def list_by_company(self, company_id: str) -> list[MutuelleType]:
        """Liste les formules mutuelle du catalogue pour une entreprise (ordre libelle)."""
        response = (
            self._supabase.table("company_mutuelle_types")
            .select("*")
            .eq("company_id", company_id)
            .order("libelle")
            .execute()
        )
        return [row_to_mutuelle_type(row) for row in (response.data or [])]

    def get_by_id(
        self,
        mutuelle_type_id: str,
        company_id: str | None = None,
    ) -> MutuelleType | None:
        """Retourne une formule par id ; si company_id fourni, filtre dessus."""
        query = (
            self._supabase.table("company_mutuelle_types")
            .select("*")
            .eq("id", mutuelle_type_id)
        )
        if company_id is not None:
            query = query.eq("company_id", company_id)
        response = query.single().execute()
        if not response.data:
            return None
        return row_to_mutuelle_type(response.data)

    def find_by_company_and_libelle(
        self,
        company_id: str,
        libelle: str,
        exclude_id: str | None = None,
    ) -> MutuelleType | None:
        """Retourne une formule avec ce (company_id, libelle) si elle existe."""
        query = (
            self._supabase.table("company_mutuelle_types")
            .select("*")
            .eq("company_id", company_id)
            .eq("libelle", libelle)
        )
        if exclude_id is not None:
            query = query.neq("id", exclude_id)
        response = query.execute()
        if not response.data or len(response.data) == 0:
            return None
        return row_to_mutuelle_type(response.data[0])

    def create(self, entity: MutuelleType, created_by: str) -> MutuelleType:
        """Crée une formule ; retourne l’entité avec id/created_at renseignés."""
        row = mutuelle_type_to_row(entity)
        row["created_by"] = created_by
        if "id" in row:
            del row["id"]
        if "created_at" in row:
            del row["created_at"]
        if "updated_at" in row:
            del row["updated_at"]
        response = self._supabase.table("company_mutuelle_types").insert(row).execute()
        if not response.data:
            raise RuntimeError("Insert mutuelle_type returned no data")
        return row_to_mutuelle_type(response.data[0])

    def update(
        self,
        mutuelle_type_id: str,
        data: dict[str, Any],
    ) -> MutuelleType | None:
        """Met à jour une formule ; retourne l’entité mise à jour ou None."""
        response = (
            self._supabase.table("company_mutuelle_types")
            .update(data)
            .eq("id", mutuelle_type_id)
            .execute()
        )
        if not response.data:
            return None
        return row_to_mutuelle_type(response.data[0])

    def delete(self, mutuelle_type_id: str) -> bool:
        """Supprime une formule. Retourne True si supprimée."""
        self._supabase.table("company_mutuelle_types").delete().eq(
            "id", mutuelle_type_id
        ).execute()
        return True

    def list_employee_ids(self, mutuelle_type_id: str) -> list[str]:
        """Liste les employee_id associés (table employee_mutuelle_types)."""
        response = (
            self._supabase.table("employee_mutuelle_types")
            .select("employee_id")
            .eq("mutuelle_type_id", mutuelle_type_id)
            .execute()
        )
        return [a["employee_id"] for a in (response.data or [])]

    def validate_employee_ids_belong_to_company(
        self, company_id: str, employee_ids: list[str]
    ) -> list[str]:
        """Retourne la sous-liste des employee_ids qui appartiennent à l’entreprise."""
        if not employee_ids:
            return []
        response = (
            self._supabase.table("employees")
            .select("id")
            .eq("company_id", company_id)
            .in_("id", employee_ids)
            .execute()
        )
        return [r["id"] for r in (response.data or [])]

    def set_employee_associations(
        self,
        mutuelle_type_id: str,
        employee_ids: list[str],
        created_by: str,
        company_id: str,
    ) -> None:
        """Remplace les associations et sync specificites_paie.mutuelle des employés."""
        current = self.list_employee_ids(mutuelle_type_id)
        current_set = set(current)
        new_set = set(employee_ids)
        to_remove = current_set - new_set
        to_add = new_set - current_set
        if to_remove:
            self._supabase.table("employee_mutuelle_types").delete().eq(
                "mutuelle_type_id", mutuelle_type_id
            ).in_("employee_id", list(to_remove)).execute()
            for emp_id in to_remove:
                self._sync_employee_mutuelle_remove(emp_id, mutuelle_type_id)
        if to_add:
            associations = [
                {
                    "employee_id": emp_id,
                    "mutuelle_type_id": mutuelle_type_id,
                    "created_by": created_by,
                }
                for emp_id in to_add
            ]
            self._supabase.table("employee_mutuelle_types").insert(
                associations
            ).execute()
            for emp_id in to_add:
                self._sync_employee_mutuelle_add(emp_id, mutuelle_type_id)

    def remove_employee_associations_and_sync_specificites(
        self,
        mutuelle_type_id: str,
        employee_ids: list[str],
    ) -> None:
        """Retire les associations et met à jour specificites_paie.mutuelle des employés."""
        if not employee_ids:
            return
        self._supabase.table("employee_mutuelle_types").delete().eq(
            "mutuelle_type_id", mutuelle_type_id
        ).in_("employee_id", employee_ids).execute()
        for emp_id in employee_ids:
            self._sync_employee_mutuelle_remove(emp_id, mutuelle_type_id)

    def _sync_employee_mutuelle_add(
        self, employee_id: str, mutuelle_type_id: str
    ) -> None:
        """Ajoute mutuelle_type_id dans specificites_paie.mutuelle de l’employé."""
        emp_res = (
            self._supabase.table("employees")
            .select("specificites_paie")
            .eq("id", employee_id)
            .single()
            .execute()
        )
        if not emp_res.data:
            return
        specificites = emp_res.data.get("specificites_paie", {}) or {}
        mutuelle_spec = specificites.get("mutuelle", {})
        mutuelle_type_ids = list(mutuelle_spec.get("mutuelle_type_ids", []))
        if mutuelle_type_id not in mutuelle_type_ids:
            mutuelle_type_ids.append(mutuelle_type_id)
        mutuelle_spec["mutuelle_type_ids"] = mutuelle_type_ids
        mutuelle_spec["adhesion"] = len(mutuelle_type_ids) > 0
        specificites["mutuelle"] = mutuelle_spec
        self._supabase.table("employees").update(
            {"specificites_paie": specificites}
        ).eq("id", employee_id).execute()

    def _sync_employee_mutuelle_remove(
        self, employee_id: str, mutuelle_type_id: str
    ) -> None:
        """Retire mutuelle_type_id de specificites_paie.mutuelle de l’employé."""
        emp_res = (
            self._supabase.table("employees")
            .select("specificites_paie")
            .eq("id", employee_id)
            .single()
            .execute()
        )
        if not emp_res.data:
            return
        specificites = emp_res.data.get("specificites_paie", {}) or {}
        mutuelle_spec = specificites.get("mutuelle", {})
        mutuelle_type_ids = list(mutuelle_spec.get("mutuelle_type_ids", []))
        if mutuelle_type_id in mutuelle_type_ids:
            mutuelle_type_ids.remove(mutuelle_type_id)
        mutuelle_spec["mutuelle_type_ids"] = mutuelle_type_ids
        mutuelle_spec["adhesion"] = len(mutuelle_type_ids) > 0
        specificites["mutuelle"] = mutuelle_spec
        self._supabase.table("employees").update(
            {"specificites_paie": specificites}
        ).eq("id", employee_id).execute()
