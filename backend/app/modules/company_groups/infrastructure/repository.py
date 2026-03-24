"""
Repository company_groups — accès table company_groups, companies, user_company_accesses, profiles.
Implémente ICompanyGroupRepository. Logique extraite de api/routers/company_groups.py ; comportement identique.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.company_groups.domain.interfaces import ICompanyGroupRepository
from app.modules.company_groups.infrastructure.queries import (
    fetch_all_active_groups_ordered,
    fetch_companies_by_group_id,
    fetch_companies_for_group_stats,
    fetch_companies_without_group,
    fetch_company_effectif_by_group_id,
    fetch_company_ids_by_group_id,
    fetch_group_by_id_with_companies,
    fetch_group_company_ids_for_permission_check,
    fetch_groups_with_companies,
)
from app.modules.company_groups.infrastructure.user_lookup import user_lookup_provider


class CompanyGroupRepository(ICompanyGroupRepository):
    """Implémentation des accès DB pour le module company_groups."""

    def get_by_id_with_companies(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Retourne un groupe par id avec ses entreprises (nested companies)."""
        return fetch_group_by_id_with_companies(group_id)

    def list_groups_with_companies(
        self, company_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Liste les groupes avec leurs entreprises.
        Si company_ids is None (super_admin) : tous les groupes actifs.
        Sinon : groupes ayant au moins une company dans company_ids (companies!inner).
        """
        return fetch_groups_with_companies(company_ids)

    def list_all_active_ordered(self) -> List[Dict[str, Any]]:
        """Liste tous les groupes actifs triés par group_name (super admin)."""
        return fetch_all_active_groups_ordered()

    def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Crée un groupe. Retourne la ligne créée."""
        res = supabase.table("company_groups").insert(data).execute()
        if not res.data:
            return None
        return res.data[0]

    def update(self, group_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Met à jour un groupe. Retourne la ligne mise à jour."""
        res = supabase.table("company_groups").update(data).eq("id", group_id).execute()
        if not res.data:
            return None
        return res.data[0]

    def exists(self, group_id: str) -> bool:
        """Vérifie qu'un groupe existe."""
        res = supabase.table("company_groups").select("id").eq("id", group_id).execute()
        return bool(res.data)

    def set_company_group(self, company_id: str, group_id: Optional[str]) -> bool:
        """Associe ou dissocie une entreprise à un groupe (update companies.group_id)."""
        res = (
            supabase.table("companies")
            .update({"group_id": group_id})
            .eq("id", company_id)
            .execute()
        )
        return bool(res.data)

    def set_company_group_with_current(
        self,
        company_id: str,
        group_id: Optional[str],
        current_group_id: Optional[str],
    ) -> bool:
        """Met à jour group_id d'une entreprise en vérifiant qu'elle est dans current_group_id."""
        q = (
            supabase.table("companies")
            .update({"group_id": group_id})
            .eq("id", company_id)
        )
        if current_group_id is not None:
            q = q.eq("group_id", current_group_id)
        res = q.execute()
        return bool(res.data)

    def get_company_ids_by_group_id(self, group_id: str) -> List[str]:
        """Liste les IDs d'entreprises d'un groupe (actives)."""
        return fetch_company_ids_by_group_id(group_id)

    def get_companies_by_group_id(
        self, group_id: str, columns: str = "id, company_name, siret, effectif, is_active"
    ) -> List[Dict[str, Any]]:
        """Liste les entreprises d'un groupe (super admin)."""
        return fetch_companies_by_group_id(group_id, columns)

    def get_companies_without_group(
        self, columns: str = "id, company_name, siret, effectif"
    ) -> List[Dict[str, Any]]:
        """Liste les entreprises sans groupe (group_id null)."""
        return fetch_companies_without_group(columns)

    def get_companies_for_group_stats(
        self, group_id: str, columns: str = "id, company_name, siret"
    ) -> List[Dict[str, Any]]:
        """Entreprises du groupe pour stats (consolidated, etc.)."""
        return fetch_companies_for_group_stats(group_id, columns)

    def get_group_company_ids_for_permission_check(self, group_id: str) -> List[str]:
        """IDs des entreprises du groupe (pour vérifier admin de toutes)."""
        return fetch_group_company_ids_for_permission_check(group_id)

    def get_groups_with_company_and_effectif(
        self, groups: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Pour chaque groupe : company_count et total_employees (effectif)."""
        result = []
        for g in groups:
            data = fetch_company_effectif_by_group_id(g["id"])
            company_count = len(data)
            total_employees = sum((c.get("effectif") or 0) for c in data)
            result.append({
                "id": g["id"],
                "group_name": g["group_name"],
                "description": g.get("description"),
                "created_at": g["created_at"],
                "company_count": company_count,
                "total_employees": total_employees,
            })
        return result

    # --- user_company_accesses + profiles + auth (super admin) ---

    def get_user_accesses_for_companies(
        self, company_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Accès user_company_accesses pour des company_ids, avec profiles et companies."""
        if not company_ids:
            return []
        res = (
            supabase.table("user_company_accesses")
            .select(
                "user_id, company_id, role, profiles(first_name, last_name), companies(company_name)"
            )
            .in_("company_id", company_ids)
            .execute()
        )
        return res.data or []

    def get_existing_user_accesses(
        self, user_id: str, company_ids: List[str]
    ) -> Dict[str, str]:
        """Accès existants (company_id -> role) pour un user et des companies."""
        if not company_ids:
            return {}
        res = (
            supabase.table("user_company_accesses")
            .select("company_id, role")
            .eq("user_id", user_id)
            .in_("company_id", company_ids)
            .execute()
        )
        return {acc["company_id"]: acc["role"] for acc in (res.data or [])}

    def update_user_profile(
        self, user_id: str, first_name: Optional[str], last_name: Optional[str]
    ) -> None:
        """Met à jour first_name / last_name dans profiles."""
        updates = {}
        if first_name is not None:
            updates["first_name"] = first_name
        if last_name is not None:
            updates["last_name"] = last_name
        if not updates:
            return
        supabase.table("profiles").update(updates).eq("id", user_id).execute()

    def insert_user_company_access(
        self, user_id: str, company_id: str, role: str, is_primary: bool
    ) -> None:
        """Insère un accès user_company_accesses."""
        supabase.table("user_company_accesses").insert({
            "user_id": user_id,
            "company_id": company_id,
            "role": role,
            "is_primary": is_primary,
        }).execute()

    def update_user_company_access_role(
        self, user_id: str, company_id: str, role: str
    ) -> None:
        """Met à jour le rôle d'un accès."""
        supabase.table("user_company_accesses").update({"role": role}).eq(
            "user_id", user_id
        ).eq("company_id", company_id).execute()

    def delete_user_company_accesses(
        self, user_id: str, company_ids: List[str]
    ) -> int:
        """Supprime les accès d'un utilisateur pour les companies données. Retourne le nombre supprimé."""
        if not company_ids:
            return 0
        res = (
            supabase.table("user_company_accesses")
            .delete()
            .eq("user_id", user_id)
            .in_("company_id", company_ids)
            .execute()
        )
        return len(res.data or [])

    def count_user_accesses(self, user_id: str) -> int:
        """Nombre d'accès existants pour un utilisateur (pour is_primary)."""
        res = (
            supabase.table("user_company_accesses")
            .select("id")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return 1 if (res.data and len(res.data) > 0) else 0

    def get_detailed_accesses_for_companies(
        self, company_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """user_company_accesses avec profiles pour detailed-user-accesses."""
        if not company_ids:
            return []
        res = (
            supabase.table("user_company_accesses")
            .select(
                "user_id, company_id, role, is_primary, profiles(first_name, last_name)"
            )
            .in_("company_id", company_ids)
            .execute()
        )
        return res.data or []

    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Délègue à IUserLookupProvider (compatibilité appel application)."""
        return user_lookup_provider.get_user_by_email(email)

    @staticmethod
    def get_user_emails_map(user_ids: List[str]) -> Dict[str, str]:
        """Délègue à IUserLookupProvider (compatibilité appel application)."""
        return user_lookup_provider.get_user_emails_map(user_ids)


company_group_repository = CompanyGroupRepository()
